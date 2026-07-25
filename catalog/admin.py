from django.contrib import admin

from .models import AnswerOption, Question, Section, Subtopic


class SubtopicInline(admin.TabularInline):
    model = Subtopic
    extra = 0


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "order")
    inlines = [SubtopicInline]


@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "order")
    list_filter = ("section",)


class AnswerOptionInline(admin.TabularInline):
    model = AnswerOption
    extra = 4


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "subtopic", "kind", "source", "is_placeholder", "active")
    list_filter = ("subtopic__section", "source", "is_placeholder", "kind", "active")
    search_fields = ("stem", "passage")
    inlines = [AnswerOptionInline]
