from django.contrib import admin

from .models import Round, RoundItem, VocabProfile, Word, WordPack, WordProgress


@admin.register(WordPack)
class WordPackAdmin(admin.ModelAdmin):
    list_display = ("slug", "title")


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    """Read-mostly: the pack files are the source, and load_vocab overwrites
    any edit made here on the next deploy. Edit vocab/data/*.json instead."""

    list_display = ("headword", "pos", "year", "group", "active")
    list_filter = ("active", "pos", "year", "packs")
    search_fields = ("headword", "group", "definition")
    filter_horizontal = ("packs",)


@admin.register(VocabProfile)
class VocabProfileAdmin(admin.ModelAdmin):
    list_display = ("pupil", "xp", "current_streak", "best_streak", "last_played_on")
    search_fields = ("pupil__email", "pupil__full_name")


@admin.register(WordProgress)
class WordProgressAdmin(admin.ModelAdmin):
    list_display = ("pupil", "word", "box", "due_on", "times_seen", "times_correct")
    list_filter = ("box",)
    search_fields = ("pupil__email", "word__headword")


class RoundItemInline(admin.TabularInline):
    model = RoundItem
    extra = 0


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("pupil", "kind", "pack", "started_at", "finished_at", "xp_awarded")
    list_filter = ("kind", "pack")
    inlines = [RoundItemInline]
