"""{% wizard level pose size %}: the Word Wizard, inline. See vocab/wizard_art.py."""
from django import template
from django.utils.safestring import mark_safe

from vocab.wizard_art import figure

register = template.Library()


@register.simple_tag
def wizard(level, pose="idle", size="md", label=None):
    return mark_safe(figure(int(level or 1), pose=pose, size=size, label=label))
