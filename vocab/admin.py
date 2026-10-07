from django.contrib import admin

from .models import Round, RoundItem, VocabProfile, Word, WordPack, WordProgress


FROM_FILES = (
    "Read only. Words and packs come from vocab/data/*.json, and load_vocab "
    "rewrites them from those files on every deploy, so a change made here would "
    "silently revert. Edit the JSON file, check it with "
    "python3 vocab/validate_words.py, and deploy."
)


class FromFilesAdmin(admin.ModelAdmin):
    """Everything visible, nothing editable, nothing added or deleted here.

    An added word would be retired by the next load_vocab, a deleted one
    recreated, and an edited one reverted.
    """

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.get_fields()
                if f.concrete and not f.auto_created] + ["id"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WordPack)
class WordPackAdmin(FromFilesAdmin):
    list_display = ("slug", "title")
    fieldsets = ((None, {"fields": ("slug", "title"), "description": FROM_FILES}),)


@admin.register(Word)
class WordAdmin(FromFilesAdmin):
    list_display = ("headword", "pos", "year", "group", "active")
    list_filter = ("active", "pos", "year", "packs")
    search_fields = ("headword", "group", "definition")
    fieldsets = (
        (None, {"fields": ("headword", "pos", "year", "group", "packs", "active"),
                "description": FROM_FILES}),
        ("Meaning", {"fields": ("definition", "synonyms", "example")}),
        ("Fill the gap", {"fields": ("gap_frame", "gap_distractors")}),
        (None, {"fields": ("updated_at",)}),
    )

    def changelist_view(self, request, extra_context=None):
        extra_context = {**(extra_context or {}), "title": "Words (read only: edit vocab/data/*.json)"}
        return super().changelist_view(request, extra_context=extra_context)


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
