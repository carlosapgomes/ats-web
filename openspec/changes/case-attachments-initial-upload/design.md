# Design: Anexos clínicos no upload inicial NIR

## Estado atual

O sistema possui upload NIR em `apps/intake/` com seleção múltipla de PDFs principais. Cada PDF principal cria um `Case` independente e salva o arquivo em `Case.pdf_file`.

Fluxo atual resumido:

```text
POST /cases/ com N PDFs principais
→ process_uploaded_files(files, user)
→ para cada PDF: cria Case, salva pdf_file, start_processing(), enqueue_pdf_extraction()
→ worker extrai texto do pdf_file
→ barreira de relatório de regulação
→ pipeline LLM
→ WAIT_DOCTOR
```

A tela médica (`templates/doctor/decision.html`) mostra:

1. formulário de decisão;
2. relatório técnico da IA;
3. texto extraído;
4. PDF principal;
5. demais informações/timeline conforme telas read-only.

Não existe modelo de anexo.

## Decisões

### D1. Anexos são artefatos do caso, não estados FSM

Criar `CaseAttachment` relacionado a `Case`. Não criar novos estados nem transições.

Motivos:

- anexos não alteram a etapa do fluxo;
- o caso continua sendo conduzido pelo PDF principal;
- a auditoria via `CaseEvent` registra a inclusão;
- preserva os 17 estados e a separação de funções.

### D2. Anexos só no upload inicial com exatamente 1 PDF principal

Regra:

```text
len(pdf_files) == 1 → anexos permitidos
len(pdf_files) != 1 → anexos não permitidos
```

Se houver anexos com múltiplos PDFs principais, retornar erro/mensagem clara e não associar anexos ambiguamente.

Motivo: no bulk upload não há relação confiável entre anexo e paciente/caso.

### D3. Primeiro change não processa anexos pela IA

Neste change, anexos são evidência humana para o médico. O pipeline continua usando somente `Case.pdf_file`.

Motivos:

- menor risco;
- evita misturar documentos não padronizados na barreira de regulação;
- mantém LLM1/LLM2 estáveis;
- permite entregar valor operacional imediato.

Mensagem de UI recomendada:

```text
Anexos enviados pelo NIR — não analisados automaticamente pela IA.
```

### D4. Modelo `CaseAttachment`

Modelo recomendado em `apps/cases/models.py`:

```python
class CaseAttachment(models.Model):
    attachment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to=case_attachment_upload_to)
    original_filename = models.CharField(max_length=255)
    stored_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="case_attachments_uploaded")
    created_at = models.DateTimeField(auto_now_add=True)
    is_suppressed = models.BooleanField(default=False, db_index=True)
    suppressed_at = models.DateTimeField(null=True, blank=True)
    suppressed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="case_attachments_suppressed")
    suppression_reason = models.TextField(blank=True)
    upload_phase = models.CharField(max_length=20, default="initial")  # initial | supplemental
    uploaded_when_case_status = models.CharField(max_length=30, blank=True)
    note = models.TextField(blank=True)
```

Índices sugeridos:

- `(case, created_at)` para ordenação de exibição;
- `sha256` para auditoria/deduplicação futura, sem bloquear duplicatas neste change.

Não adicionar campos de classificação/OCR ainda. Isso é YAGNI para o primeiro change.

Adicionar campos de supressão desde o modelo inicial é deliberado: envio incorreto de anexo de outro paciente é um edge case previsível, e as telas devem conseguir ocultar/bloquear anexos suprimidos sem deleção silenciosa.

Adicionar `upload_phase`, `uploaded_when_case_status` e `note` desde o modelo inicial também é deliberado: anexos faltantes podem precisar ser enviados depois do upload inicial, desde que o médico ainda não tenha decidido. Isso deve ficar rastreável e distinguível na UI/timeline.

### D5. Caminho seguro no filesystem

Não usar o nome original como nome de armazenamento.

Usar função `upload_to`, por exemplo:

```python
def case_attachment_upload_to(instance: CaseAttachment, filename: str) -> str:
    ext = validated_or_normalized_extension(filename, instance.content_type)
    return f"case_attachments/{instance.case_id}/{instance.attachment_id}{ext}"
```

Exemplo:

```text
media/case_attachments/<case_id>/<attachment_id>.pdf
media/case_attachments/<case_id>/<attachment_id>.jpg
media/case_attachments/<case_id>/<attachment_id>.png
```

`original_filename` deve ser usado apenas para exibição/auditoria.

### D6. Validação por assinatura simples + extensão/content-type

Aceitar somente:

| Extensões | Content-type esperado | Categoria |
| --- | --- | --- |
| `.pdf` | `application/pdf` | PDF |
| `.jpg`, `.jpeg` | `image/jpeg` | imagem |
| `.png` | `image/png` | imagem |

A validação deve combinar extensão normalizada e content-type quando disponível. Se o content-type vier vazio ou genérico do navegador, a extensão ainda pode ser usada, mas registrar isso no relatório do slice.

Limites:

```python
INTAKE_MAX_ATTACHMENTS_PER_CASE = 10
INTAKE_MAX_ATTACHMENT_BYTES_PER_FILE = 20 * 1024 * 1024
INTAKE_MAX_ATTACHMENT_BYTES_PER_CASE = 200 * 1024 * 1024
```

### D7. Limites de POST e rede

Configuração atual:

```python
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
INTAKE_MAX_UPLOAD_BYTES_PER_FILE = 20 * 1024 * 1024
INTAKE_MAX_UPLOAD_BYTES_PER_BATCH = 600 * 1024 * 1024
```

O upload NIR usa conexão intranet direta ao IP interno do servidor, não Cloudflare. Logo, Cloudflare não deve limitar o request NIR.

Pontos para o implementador validar:

- Django upload handlers conseguem receber 1 PDF principal + até 10 anexos de 20 MB.
- O limite de batch atual de 600 MB cobre os ~220 MB máximos esperados.
- `DATA_UPLOAD_MAX_MEMORY_SIZE` não deve ser usado como substituto da validação de arquivos; se testes práticos mostrarem bloqueio, ajustar explicitamente e documentar no relatório.

### D8. Serviços de domínio/intake

Evitar lógica grande em views.

Preferir helpers pequenos em `apps/intake/services.py` ou módulo coeso:

```python
def validate_attachment_file(file: UploadedFile) -> AttachmentMetadata: ...

def create_case_attachment(*, case: Case, uploaded_file: UploadedFile, user: User) -> CaseAttachment: ...

def process_uploaded_files(files: list[UploadedFile], user: User, attachments: list[UploadedFile] | None = None) -> tuple[list[Case], list[str]]: ...
```

Regra importante:

- se `attachments` não vazio e `len(files) != 1`, rejeitar anexos com erro claro;
- se qualquer anexo for inválido, preferir falha transacional do upload único com anexos, para não criar caso incompleto sem os anexos esperados.

### D9. Auditoria

Registrar `CaseEvent` para cada anexo salvo:

```text
CASE_ATTACHMENT_ADDED
```

Payload sugerido:

```json
{
  "attachment_id": "...",
  "original_filename": "laudo-usg.pdf",
  "content_type": "application/pdf",
  "size_bytes": 123456,
  "sha256": "..."
}
```

Não registrar conteúdo clínico completo no evento.

### D10. Views protegidas para servir anexos

Servir anexos por views protegidas, por exemplo:

```text
/doctor/cases/<case_id>/attachments/<attachment_id>/
/cases/<case_id>/attachments/<attachment_id>/
```

Ou helper compartilhado em `apps/cases` se houver oportunidade enxuta. Manter autorização por papel/escopo:

- `doctor`: pode ver anexos de caso em `WAIT_DOCTOR` ou caso que ele decidiu, conforme telas médicas existentes.
- `nir`: pode ver anexos em casos operacionais não `CLEANED`.
- `manager/admin`: visualização futura via dashboard pode ser feita no slice 002 se necessário.

Não expor `MEDIA_URL` diretamente para PHI.

### D11. UI médica

Na tela médica, ordem recomendada:

1. texto extraído;
2. PDF principal;
3. anexos, um collapsible por anexo;
4. timeline quando aplicável.

Para PDF:

```html
<embed src="..." type="application/pdf">
```

Para imagem:

```html
<img src="..." class="img-fluid" alt="Anexo ...">
```

Mostrar metadados:

- nome original;
- tipo;
- tamanho;
- data/hora de upload;
- usuário que anexou.

### D12. UI NIR upload

O JavaScript de upload deve detectar a quantidade de PDFs principais selecionados:

- 0 arquivos: anexos ocultos/desabilitados;
- 1 arquivo: anexos visíveis/habilitados;
- >1 arquivos: anexos ocultos/desabilitados e seleção de anexos limpa.

Validação client-side é conveniência. Validação server-side é obrigatória.

Quando houver anexos, a UI deve oferecer pré-visualização antes do envio:

- PDF: preview/embed quando viável no browser, ou ao menos link/ícone com nome/tamanho;
- JPEG/PNG: thumbnail/preview;
- botão remover antes de enviar;
- checkbox obrigatório: `Confirmo que revisei os anexos e que pertencem ao mesmo paciente/caso.`

### D13. Supressão auditável de anexo incorreto

Não implementar deleção silenciosa de anexos clínicos no fluxo operacional.

Se o NIR enviou um anexo errado, o sistema deve permitir **suprimir** o anexo:

```text
anexo ativo → NIR informa motivo obrigatório → anexo suprimido
```

Efeitos:

- anexo suprimido deixa de aparecer nas telas clínicas;
- rotas protegidas operacionais retornam 404/403 para anexo suprimido;
- arquivo pode permanecer no storage para auditoria/forense, mas sem acesso clínico normal;
- registrar `CASE_ATTACHMENT_SUPPRESSED` com metadados e motivo;
- timeline pode mostrar mensagem genérica: `Um anexo foi removido pelo NIR por envio incorreto.`

Campos no `CaseAttachment`:

```python
is_suppressed = models.BooleanField(default=False)
suppressed_at = models.DateTimeField(null=True, blank=True)
suppressed_by = models.ForeignKey(User, null=True, blank=True, ...)
suppression_reason = models.TextField(blank=True)
```

Views clínicas devem filtrar `is_suppressed=False`.

### D14. Momento da supressão e mitigação operacional

Casos possíveis:

1. **Antes de `WAIT_DOCTOR`**: suprimir remove o anexo antes de qualquer visualização médica.
2. **Em `WAIT_DOCTOR` sem decisão**: suprimir bloqueia novos acessos; o médico pode já ter visto se estava com a tela aberta. Registrar evento e exibir aviso genérico.
3. **Após decisão médica**: supressão ainda pode ocultar o anexo, mas a decisão pode ter sido contaminada. A mitigação recomendada é encerramento administrativo e novo envio corrigido, não correção silenciosa do mesmo caso.

Este change implementa a supressão operacional. A política formal de reenviar/reabrir caso decidido fica fora de escopo.

### D15. Anexos complementares antes da decisão médica

Há dois cenários previsíveis:

1. caso aberto sem anexos, mas deveria ter anexos;
2. caso aberto com alguns anexos, mas faltou um ou mais.

Enquanto o médico ainda não decidiu, o NIR deve poder adicionar anexos faltantes ao **mesmo `Case`**, como anexos complementares.

Condição geral:

```text
doctor_decision vazio
status ainda antes/dependente da avaliação médica
```

Estados elegíveis sugeridos:

```text
R1_ACK_PROCESSING
EXTRACTING
LLM_STRUCT
LLM_SUGGEST
R2_POST_WIDGET
WAIT_DOCTOR
```

Ao adicionar anexo complementar:

- exigir justificativa/mensagem obrigatória;
- setar `upload_phase="supplemental"`;
- gravar `uploaded_when_case_status` com status do caso no momento;
- gravar `note` com a justificativa;
- registrar evento específico `CASE_ATTACHMENT_SUPPLEMENT_ADDED`;
- exibir ao médico badge/aviso: `Adicionado após upload inicial — não analisado automaticamente pela IA`.

Se o caso estiver em `WAIT_DOCTOR` com lock médico ativo, bloquear a inclusão e mostrar ao NIR:

```text
Este caso está reservado por Dr(a). X. Aguarde a liberação ou comunique o médico.
```

Motivo: evitar que o médico decida com uma tela já aberta sem perceber a inclusão documental.

Após decisão médica (`doctor_decision` preenchido), não adicionar anexos ao mesmo caso. A conduta segura é novo caso corrigido/reconsideração futura, com referência ao caso anterior.

### D16. Reenvio/reabertura futura

Cada upload cria um novo `Case`; cada anexo pertence a exatamente um `Case` via FK. Portanto, anexos de envios diferentes **não se misturam** e não devem ser herdados/copiados automaticamente.

Desenho futuro recomendado:

```text
Case A original com anexo errado/suprimido
Case B reenviado/corrigido com seus próprios anexos
Case B referencia Case A como caso corrigido/superseded_by
```

Essa relação formal entre casos deve ser tratada em change separado, junto com reinserção/reabertura e correção do prior-case lookup para não depender de status transitório.

### D17. Justificativa de escopo > 5 arquivos

Este change inevitavelmente cruza modelo, upload, armazenamento protegido e UI médica. Para preservar slices verticais, o Slice 001 pode tocar mais de 5 arquivos. Isso é aceito porque entregar apenas modelo ou apenas template seria horizontal e sem valor operacional. Cada slice deve, porém, evitar refactors amplos e não mexer no pipeline LLM/FSM.

## Plano de slices

### Slice 001 — MVP end-to-end de anexos no upload único e tela médica

Entrega valor completo mínimo:

```text
NIR envia 1 PDF + anexos válidos → caso salva anexos → médico abre decisão → vê anexos inline
```

Inclui modelo, migration, validação backend, upload, auditoria, URLs protegidas e visualização médica básica.

### Slice 002 — UX/operacionalização e visualização compartilhada

Aprimora a experiência:

- JS condicional robusto para anexos apenas com 1 PDF principal;
- preview de anexos com contagem/tamanho/remoção antes do submit;
- confirmação obrigatória de que anexos pertencem ao mesmo paciente/caso;
- anexos no detalhe NIR/read-only compartilhado;
- testes de limites e mensagens;
- refinamento de labels e acessibilidade.

### Slice 003 — Supressão auditável de anexo enviado incorretamente

Entrega mitigação operacional:

```text
NIR percebe anexo errado em caso operacional
→ suprime anexo com motivo obrigatório
→ anexo deixa de aparecer/ser servido
→ timeline registra evento
```

Não reabre caso decidido.

### Slice 004 — Anexos complementares antes da decisão médica

Entrega complementação documental:

```text
NIR percebe anexo faltante antes da decisão médica
→ adiciona anexo complementar com justificativa
→ se caso sem lock médico: anexo fica no mesmo Case
→ médico vê anexo complementar sinalizado
→ evento CASE_ATTACHMENT_SUPPLEMENT_ADDED registra ação
```

Não adiciona anexos após decisão médica e não cria automaticamente caso corrigido.

## Riscos e mitigação

| Risco | Mitigação |
| --- | --- |
| Ambiguidade de anexo em bulk upload | Permitir anexos somente com exatamente 1 PDF principal |
| Colisão/path traversal por nome original | Armazenar por UUID e preservar nome original só como metadado |
| PHI exposta via media | Servir por views autenticadas/autorizadas |
| Médico achar que IA leu anexos | Aviso explícito na UI |
| Anexo de outro paciente enviado por engano | Pré-visualização + confirmação antes do envio + supressão auditável após envio |
| Anexo faltante percebido antes da decisão médica | Fluxo estruturado de anexo complementar no mesmo Case, com justificativa e evento específico |
| Anexo faltante percebido enquanto médico avalia | Bloquear inclusão se houver lock médico ativo e orientar aguardar/liberar/comunicar |
| Upload grande falhar por limite técnico | Testar intranet com payload real; limites explícitos de arquivo/anexo |
| Slice horizontal sem valor | Slice 001 deve ser end-to-end mesmo tocando mais arquivos |
| Escopo fugir para OCR/LLM | Manter processamento de anexos fora do change |

## Limitações aceitas (não bloqueantes)

Estas limitações foram avaliadas durante a implementação e aceitas como
aceitáveis para este change. Não são bugs e não comprometem integridade de
dados; documentam trade-offs conscientes.

### L1. Lote de anexos complementares sem atomicidade transacional de batch

O POST de anexo complementar pode enviar vários arquivos numa única
requisição. Cada arquivo é commitado em sua própria `transaction.atomic()`
em `add_supplemental_case_attachment`. Não há uma transação única envolvendo
todo o lote.

Cenário que poderia levar a inserção parcial: a elegibilidade do caso
(`doctor_decision` vazio, status elegível, sem lock médico) mudar por ação
concorrente **entre** duas inserções do mesmo lote (janela de milissegundos).

Mitigações existentes que reduzem a janela a praticamente zero em fluxo
normal:

- Tipo e tamanho de cada arquivo são validados pela view **antes** do loop.
- Limite de anexos por caso é validado pela view para o lote inteiro **antes**
  do loop e, em defesa em profundidade, também pelo serviço a cada inserção.
- Elegibilidade é verificada pelo serviço a cada inserção dentro de
  `select_for_update()`.

Pior caso realista: 1 anexo complementar é inserido num caso que, milissegundos
depois, recebe decisão médica. Não há corrupção de dados; o anexo fica
registrado com auditoria (`CASE_ATTACHMENT_SUPPLEMENT_ADDED`) e a auditoria
permanece fonte de verdade. Corrigir exige refactor de API do serviço
(split `assert_eligibility` + persist sem `atomic` própria, ou novo método
de lote), com risco de regressão em código clínico estável. Avaliado como
não justificado neste change.

## Futuro fora deste change

Um change futuro deve classificar/processar anexos para IA:

- PDF textual;
- PDF escaneado/foto de texto;
- foto de texto;
- foto clínica;
- US/Tomografia/RX;
- outro/indeterminado.

Esse change futuro decidirá se o conteúdo extraído dos anexos entra no LLM2 ou em uma terceira chamada LLM, possivelmente com prompts específicos pelo tipo de exame detectado no LLM1.

Outro change futuro deve tratar reenvio/reabertura/reconsideração de casos, incluindo relação formal entre `Case` original e `Case` corrigido. Até lá, cada envio mantém sua lista própria de anexos e anexos não são misturados entre casos.
