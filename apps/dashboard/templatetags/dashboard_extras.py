"""Template tags para o app dashboard."""

from django import template

register = template.Library()


@register.filter
def lookup(d: dict[str, str], key: str) -> str:
    """Retorna o valor de um dicionário pela chave.

    Uso no template:
        {{ my_dict|lookup:key }}
    """
    return d.get(key, key)
