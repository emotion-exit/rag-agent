<script setup lang="ts">
import { computed } from 'vue';
import MarkdownIt from 'markdown-it';
import {
  LoadingOutlined,
  WarningOutlined,
  ReloadOutlined,
  SaveOutlined
} from '@ant-design/icons-vue';
import { OButton, OEmptyState } from '@/orange-ui';
import type {
  NoteDetail,
  NoteListItem,
  NoteRevisionDraft,
  NoteSourceSummary
} from '@/types/notes';

const props = defineProps<{
  noteDetailLoading: boolean;
  selectedNoteSummary: NoteListItem | null;
  selectedNoteDetail: NoteDetail | null;
  revisionDraft: NoteRevisionDraft | null;
  revisionDraftLoading: boolean;
  revisionSaving: boolean;
}>();

defineEmits<{
  openSource: [source: NoteSourceSummary];
  generateRevisionDraft: [];
  discardRevisionDraft: [];
  saveRevisionDraft: [];
}>();

const noteMarkdown = new MarkdownIt({
  breaks: true,
  linkify: false,
  html: false
});

noteMarkdown.renderer.rules.link_open = () => '';
noteMarkdown.renderer.rules.link_close = () => '';

const renderedSelectedNoteAnswer = computed(() => {
  const answer =
    props.selectedNoteDetail?.current_revision?.answer?.trim() || '';
  return answer ? noteMarkdown.render(answer) : '';
});

const renderedRevisionDraftAnswer = computed(() => {
  const answer = props.revisionDraft?.answer?.trim() || '';
  return answer ? noteMarkdown.render(answer) : '';
});
</script>

<template>
  <section
    class="flex h-full min-h-0 flex-col rounded-2xl border border-zinc-200/60 bg-white px-6 py-5">
    <template v-if="noteDetailLoading">
      <div class="space-y-4">
        <div class="h-5 w-1/3 animate-pulse rounded-full bg-zinc-200"></div>
        <div class="h-4 w-2/3 animate-pulse rounded-full bg-zinc-100"></div>
        <div class="h-28 animate-pulse rounded-3xl bg-zinc-100"></div>
        <div class="h-32 animate-pulse rounded-3xl bg-zinc-100"></div>
      </div>
    </template>

    <template v-else-if="selectedNoteSummary?.status === 'pending'">
      <div class="flex h-full min-h-105 items-center justify-center">
        <div class="max-w-md text-center">
          <div
            class="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-zinc-100 text-zinc-600">
            <LoadingOutlined class="animate-spin text-lg" />
          </div>
          <div class="mt-5 text-lg font-semibold text-zinc-900">
            正在保存笔记
          </div>
          <p class="mt-2 text-sm leading-7 text-zinc-500">
            当前条目正在后台写入，完成后这里会自动显示正式内容。你可以继续聊天，不会受影响。
          </p>
        </div>
      </div>
    </template>

    <template v-else-if="selectedNoteSummary?.status === 'failed'">
      <div class="flex h-full min-h-105 items-center justify-center">
        <div class="max-w-md text-center">
          <div
            class="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-red-100 text-red-600">
            <WarningOutlined class="text-lg" />
          </div>
          <div class="mt-5 text-lg font-semibold text-zinc-900">
            笔记保存失败
          </div>
          <p class="mt-2 text-sm leading-7 text-zinc-500">
            {{ selectedNoteSummary.last_error || '请稍后重新尝试保存。' }}
          </p>
        </div>
      </div>
    </template>

    <template v-else-if="selectedNoteDetail?.current_revision">
      <div class="flex h-full min-h-0 flex-col">
        <div class="shrink-0 border-b border-zinc-100 pb-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 class="text-2xl font-semibold tracking-tight text-zinc-950">
                {{ selectedNoteDetail.current_revision.title }}
              </h3>
              <div
                class="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
                <span
                  v-if="selectedNoteDetail.note.knowledge_space"
                  class="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 font-medium text-zinc-700">
                  {{ selectedNoteDetail.note.knowledge_space }}
                </span>
                <span>保存时间：{{ selectedNoteDetail.note.updated_at }}</span>
              </div>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <OButton
                variant="secondary"
                size="sm"
                class="rounded-full px-3"
                :loading="revisionDraftLoading"
                :disabled="revisionSaving"
                @click="$emit('generateRevisionDraft')">
                <ReloadOutlined />
                重新生成候选答案
              </OButton>
              <OButton
                v-if="revisionDraft"
                size="sm"
                class="rounded-full px-3"
                :loading="revisionSaving"
                @click="$emit('saveRevisionDraft')">
                <SaveOutlined />
                确认覆盖笔记
              </OButton>
            </div>
          </div>
        </div>

        <div class="mt-5 min-h-0 flex-1 overflow-y-auto pr-1 pb-6">
          <div
            v-if="revisionDraftLoading"
            class="space-y-3 rounded-2xl bg-zinc-50 px-5 py-4">
            <div class="text-sm font-medium text-zinc-700">
              正在生成新的候选内容
            </div>
            <div class="h-4 w-1/3 animate-pulse rounded-full bg-zinc-200"></div>
            <div class="h-24 animate-pulse rounded-2xl bg-white"></div>
          </div>

          <template v-else-if="revisionDraft">
            <div
              class="rounded-2xl border border-amber-200/60 bg-amber-50/45 px-5 py-4">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div class="text-sm font-medium text-amber-900">
                    已生成新的候选内容
                  </div>
                  <div class="mt-1 text-xs text-amber-800/80">
                    生成时间：{{ revisionDraft.generated_at }}
                    <span v-if="revisionSaving">，正在异步覆盖当前笔记…</span>
                  </div>
                </div>
                <OButton
                  variant="ghost"
                  size="sm"
                  class="rounded-full px-3"
                  :disabled="revisionSaving"
                  @click="$emit('discardRevisionDraft')">
                  丢弃候选
                </OButton>
              </div>

              <div
                class="o-markdown mt-4 rounded-2xl border border-amber-200/60 bg-white px-5 py-5"
                v-html="renderedRevisionDraftAnswer"></div>

              <div class="mt-5">
                <div
                  class="text-xs font-bold uppercase tracking-[0.14em] text-amber-700">
                  候选来源
                </div>
                <div
                  v-if="revisionDraft.sources.length > 0"
                  class="mt-3 flex flex-wrap gap-2.5">
                  <button
                    v-for="source in revisionDraft.sources"
                    :key="`revision-source-${selectedNoteDetail.note.note_id}-${source.doc_id}-${source.chunk_index}`"
                    type="button"
                    class="flex w-52 max-w-full items-start gap-2 rounded-xl border border-amber-200 bg-white px-3 py-2 text-left text-xs text-zinc-700 transition-all duration-200 hover:border-amber-300 hover:bg-amber-50"
                    @click="$emit('openSource', source)">
                    <span
                      class="flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-50 text-[10px] font-bold text-amber-900 ring-1 ring-amber-100">
                      {{ source.index }}
                    </span>
                    <span
                      class="flex min-w-0 flex-1 flex-col items-start gap-0.5">
                      <span class="block max-w-35 truncate">
                        {{ source.filename }}
                      </span>
                      <span
                        class="o-source-summary text-left text-[11px] text-zinc-500">
                        {{ source.summary }}
                      </span>
                    </span>
                  </button>
                </div>
                <div
                  v-else
                  class="mt-3 rounded-xl border border-dashed border-amber-200 bg-white px-4 py-4 text-sm text-zinc-500">
                  这次候选内容没有返回可展示的来源摘要。
                </div>
              </div>
            </div>
          </template>

          <div
            :class="revisionDraftLoading || revisionDraft ? 'mt-5' : ''"
            class="o-markdown rounded-2xl bg-zinc-50 px-5 py-5"
            v-html="renderedSelectedNoteAnswer"></div>

          <div class="mt-5 border-t border-zinc-100 pt-5 pb-1">
            <div
              class="text-xs font-bold uppercase tracking-[0.14em] text-zinc-500">
              引用来源
            </div>
            <div
              v-if="selectedNoteDetail.sources.length > 0"
              class="mt-3 flex flex-wrap gap-2.5">
              <button
                v-for="source in selectedNoteDetail.sources"
                :key="`note-source-${selectedNoteDetail.note.note_id}-${source.doc_id}-${source.chunk_index}`"
                type="button"
                class="flex w-52 max-w-full items-start gap-2 rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-left text-xs text-zinc-700 transition-all duration-200 hover:border-zinc-300 hover:bg-zinc-100"
                @click="$emit('openSource', source)">
                <span
                  class="flex h-5 min-w-5 items-center justify-center rounded-full bg-white text-[10px] font-bold text-zinc-950 ring-1 ring-zinc-200">
                  {{ source.index }}
                </span>
                <span class="flex min-w-0 flex-1 flex-col items-start gap-0.5">
                  <span class="block max-w-35 truncate">
                    {{ source.filename }}
                  </span>
                  <span
                    class="o-source-summary text-left text-[11px] text-zinc-500">
                    {{ source.summary }}
                  </span>
                </span>
              </button>
            </div>
            <div
              v-else
              class="mt-3 rounded-xl border border-dashed border-zinc-200 bg-zinc-50 px-4 py-4 text-sm text-zinc-500">
              当前笔记没有保存可展示的来源摘要。
            </div>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="flex h-full min-h-105 items-center justify-center">
        <OEmptyState
          title="选择一条笔记"
          description="左侧可以查看保存中的占位项，也可以打开已经完成的笔记详情。" />
      </div>
    </template>
  </section>
</template>
