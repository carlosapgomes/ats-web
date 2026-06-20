# Proposal: Anexos clínicos no upload inicial NIR

**Change ID**: `case-attachments-initial-upload`  
**Fase**: melhoria operacional NIR/médico pós-upload múltiplo  
**Risco**: PROFISSIONAL (adiciona novo artefato clínico persistido, upload multipart maior e visualização médica; não altera FSM nem pipeline LLM neste change)  
**Dependências**: `intake-nir`, `multi-pdf-async-intake`, `doctor-queue`, `nir-result-closure`

## Problema

Usuários NIR relataram que, com frequência, a unidade de origem envia documentos complementares ao relatório principal sem transcrever o conteúdo no PDF inicial. Exemplos:

- laudos complementares em PDF;
- JPEG/PNG de laudos fotografados;
- imagens clínicas ou exames de imagem que o médico precisa consultar.

Hoje o sistema aceita apenas o PDF principal (`Case.pdf_file`). O fluxo bulk de múltiplos PDFs cria um caso por arquivo, mas não há como associar documentos adicionais a um caso específico.

Isso cria risco operacional: o médico pode receber o relatório principal isolado, negar por pendência documental e só depois o NIR tentar complementar manualmente. Para fluxos futuros como CPRE, anexos serão frequentes e previsíveis.

Há também um edge case operacional inevitável: o NIR pode anexar por engano documento de outro paciente. O design deve prevenir esse erro com pré-visualização/remoção antes do envio e mitigar sua repercussão com supressão auditável após o envio.

## Objetivo

Permitir que o NIR envie anexos clínicos junto com o relatório principal quando o upload tiver exatamente um PDF principal, e permitir que o médico visualize esses anexos inline na tela de decisão.

O primeiro incremento deve preservar o fluxo atual:

```text
NIR envia 1 PDF principal + anexos opcionais
→ sistema cria Case e salva anexos
→ pipeline continua processando apenas o PDF principal
→ médico vê relatório IA + PDF principal + anexos
→ médico decide
```

## Escopo

### Funcionalidades

1. **Anexos no upload inicial**
   - Aceitar anexos somente quando o NIR envia exatamente 1 relatório principal.
   - Manter upload múltiplo de PDFs principais sem anexos.
   - Rejeitar ou ignorar com mensagem clara anexos enviados junto com múltiplos PDFs principais.

2. **Formatos e limites**
   - Formatos aceitos: PDF, JPEG/JPG e PNG.
   - Máximo: 10 anexos por caso.
   - Tamanho máximo: 20 MB por anexo.
   - Limite total recomendado para anexos por caso: 200 MB.

3. **Persistência segura**
   - Criar modelo de domínio para anexos, por exemplo `CaseAttachment`.
   - Preservar nome original como metadado.
   - Armazenar arquivo com nome derivado de UUID para evitar colisões.
   - Organizar filesystem por caso, por exemplo:

```text
media/case_attachments/<case_id>/<attachment_id>.<ext>
```

4. **Auditoria**
   - Registrar eventos append-only em `CaseEvent`, por exemplo `CASE_ATTACHMENT_ADDED`.
   - Payload deve conter metadados mínimos, sem conteúdo clínico integral.

5. **Visualização médica**
   - Na tela de decisão médica, mostrar anexos ativos após o PDF principal e antes da timeline.
   - Usar um collapsible por anexo.
   - PDF: embed inline.
   - JPEG/PNG: imagem inline responsiva.
   - Exibir nome original, tipo, tamanho e data de upload.

6. **Acesso protegido**
   - Servir anexos por views protegidas por papel/escopo, não por URL direta de media.
   - Médico deve conseguir abrir anexos ativos de casos em sua fila/decididos próprios conforme telas existentes.
   - NIR deve conseguir ver anexos ativos nos detalhes operacionais de casos não `CLEANED`.

7. **Prevenção de anexo errado**
   - Pré-visualizar anexos antes do envio.
   - Permitir remover anexos selecionados antes do submit.
   - Exigir confirmação explícita de que anexos pertencem ao mesmo paciente/caso quando houver anexos.

8. **Mitigação de anexo errado após envio**
   - Permitir supressão auditável de anexo ativo pelo NIR enquanto o caso ainda estiver operacional.
   - Anexo suprimido deixa de aparecer nas telas clínicas e deixa de ser servido por rotas operacionais.
   - Registrar evento de auditoria, por exemplo `CASE_ATTACHMENT_SUPPRESSED`, com motivo obrigatório.

9. **Complementação documental antes da decisão médica**
   - Permitir que o NIR adicione anexos complementares ao mesmo caso quando o médico ainda não decidiu.
   - Exigir justificativa/mensagem obrigatória para anexo complementar.
   - Registrar evento específico `CASE_ATTACHMENT_SUPPLEMENT_ADDED`.
   - Se o caso estiver reservado por médico em `WAIT_DOCTOR`, bloquear a inclusão e orientar o NIR a aguardar liberação ou comunicar o médico.
   - Após decisão médica, não adicionar anexos ao mesmo caso; reenvio/caso corrigido com referência ao caso original fica para change futuro.

## Fora de escopo

- Processar anexos pela IA neste change.
- OCR de imagens ou PDFs escaneados.
- Classificar anexos por tipo clínico/radiológico.
- Prompt específico para CPRE.
- Tornar anexos obrigatórios para algum tipo de exame.
- Permitir adicionar novos anexos após o caso já ter ido ao médico.
- Reabertura/reconsideração de casos negados, exceto observações de desenho futuro.
- Criar automaticamente novo caso corrigido após decisão médica.
- Alterar os 17 estados FSM.
- Criar storage externo/S3.

## Decisões de produto incorporadas

- Incluir PNG além de PDF e JPEG/JPG.
- Limitar a 10 anexos por caso.
- Usar 20 MB por arquivo.
- Visualização inline padronizada via collapsibles.
- Não tratar CPRE de forma especial no upload; o upload genérico deve servir para CPRE futuramente.
- Futuramente, anexos poderão alimentar OCR/LLM, mas isso será outro change.
- Upload NIR ocorre por IP interno/intranet direto ao servidor; Cloudflare é usado para médicos/supervisores/admin e não deve ser gargalo para upload NIR.
- Envio incorreto de anexo deve ser tratado como supressão auditável, não como deleção silenciosa.
- Reenvios/casos corrigidos não devem herdar anexos do envio anterior: cada `Case` mantém sua própria lista de anexos.
- Antes da decisão médica, anexos faltantes devem ser adicionados ao mesmo `Case` como complementares. Depois da decisão médica, o caminho seguro é novo caso corrigido/reconsideração futura.

## Critérios de sucesso

- Upload múltiplo de PDFs principais continua funcionando sem regressão.
- Upload de 1 PDF principal habilita anexos opcionais.
- Upload de múltiplos PDFs principais não permite anexos.
- PDF/JPEG/JPG/PNG válidos são salvos como anexos do caso.
- Arquivos inválidos ou acima de 20 MB são rejeitados com mensagem clara.
- Mais de 10 anexos são rejeitados.
- Nome no filesystem não colide entre casos nem dentro do mesmo caso.
- Nome original aparece para o usuário.
- Médico vê anexos ativos inline na tela de decisão.
- NIR consegue pré-visualizar e remover anexos antes de enviar.
- NIR consegue suprimir anexo ativo enviado incorretamente com motivo obrigatório.
- Anexos suprimidos não aparecem para o médico nem são servidos por rotas operacionais.
- NIR consegue adicionar anexo complementar ao mesmo caso antes da decisão médica, com justificativa obrigatória.
- Anexo complementar registra `CASE_ATTACHMENT_SUPPLEMENT_ADDED` e aparece ao médico com indicação de que foi adicionado após o upload inicial.
- Anexos não são enviados à barreira de relatório de regulação nem ao pipeline LLM.
- Eventos de auditoria existem para anexos salvos.
- Quality gate do AGENTS.md passa.
