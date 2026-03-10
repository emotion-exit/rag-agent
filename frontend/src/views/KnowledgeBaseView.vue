<script setup lang="ts">
import { ref, onMounted, h } from 'vue'
import {
  UploadOutlined,
  DeleteOutlined,
  FileTextOutlined,
  FilePdfOutlined,
  FileWordOutlined,
  DatabaseOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import type { UploadProps } from 'ant-design-vue'

interface DocumentInfo {
  doc_id: string
  filename: string
  upload_time: string
}

interface Stats {
  total_chunks: number
  total_documents: number
}

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const documents = ref<DocumentInfo[]>([])
const stats = ref<Stats>({ total_chunks: 0, total_documents: 0 })
const loading = ref(false)
const uploading = ref(false)

const columns = [
  {
    title: '文件名',
    dataIndex: 'filename',
    key: 'filename',
    ellipsis: true,
  },
  {
    title: '上传时间',
    dataIndex: 'upload_time',
    key: 'upload_time',
    width: 200,
    customRender: ({ text }: { text: string }) => {
      if (!text) return '-'
      try {
        return new Date(text).toLocaleString('zh-CN')
      } catch {
        return text
      }
    },
  },
  {
    title: '操作',
    key: 'action',
    width: 100,
    align: 'center',
  },
]

function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase()
  if (ext === 'pdf') return FilePdfOutlined
  if (ext === 'doc' || ext === 'docx') return FileWordOutlined
  return FileTextOutlined
}

async function fetchDocuments() {
  loading.value = true
  try {
    const [docsRes, statsRes] = await Promise.all([
      fetch(`${API_BASE}/api/knowledge-base/documents`),
      fetch(`${API_BASE}/api/knowledge-base/stats`),
    ])
    if (!docsRes.ok) throw new Error(`HTTP ${docsRes.status}`)
    if (!statsRes.ok) throw new Error(`HTTP ${statsRes.status}`)

    const docsData = await docsRes.json()
    const statsData = await statsRes.json()
    documents.value = docsData.documents || []
    stats.value = statsData
  } catch (err: unknown) {
    message.error('加载文档列表失败，请检查后端服务是否正常运行')
  } finally {
    loading.value = false
  }
}

async function handleUpload(options: { file: File; onSuccess?: (res: unknown) => void; onError?: (err: Error) => void }) {
  const { file, onSuccess, onError } = options
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch(`${API_BASE}/api/knowledge-base/upload`, {
      method: 'POST',
      body: formData,
    })
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || `HTTP ${response.status}`)
    }
    message.success(data.message || '上传成功')
    onSuccess?.(data)
    await fetchDocuments()
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err)
    message.error(`上传失败：${errMsg}`)
    onError?.(err instanceof Error ? err : new Error(errMsg))
  } finally {
    uploading.value = false
  }
}

async function deleteDocument(doc: DocumentInfo) {
  try {
    const response = await fetch(`${API_BASE}/api/knowledge-base/documents/${doc.doc_id}`, {
      method: 'DELETE',
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`)
    message.success(`已删除文档 "${doc.filename}"`)
    await fetchDocuments()
  } catch (err: unknown) {
    const errMsg = err instanceof Error ? err.message : String(err)
    message.error(`删除失败：${errMsg}`)
  }
}

const uploadProps: UploadProps = {
  accept: '.pdf,.doc,.docx,.txt,.md,.rst,.csv',
  multiple: true,
  showUploadList: false,
  customRequest: handleUpload as UploadProps['customRequest'],
  beforeUpload: (file) => {
    const maxSize = 20 * 1024 * 1024
    if (file.size > maxSize) {
      message.error(`文件 "${file.name}" 过大，最大支持 20 MB`)
      return false
    }
    return true
  },
}

onMounted(() => {
  fetchDocuments()
})
</script>

<template>
  <div class="kb-container">
    <!-- Stats cards -->
    <a-row :gutter="16" style="margin-bottom: 24px">
      <a-col :span="12">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="知识库文档数"
            :value="stats.total_documents"
            :prefix="h(DatabaseOutlined)"
            value-style="color: #1890ff"
          />
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card class="stat-card" :bordered="false">
          <a-statistic
            title="文本块总数"
            :value="stats.total_chunks"
            :prefix="h(FileTextOutlined)"
            value-style="color: #52c41a"
          />
        </a-card>
      </a-col>
    </a-row>

    <!-- Upload area -->
    <a-card class="upload-card" :bordered="false" title="上传文档" style="margin-bottom: 24px">
      <a-upload-dragger v-bind="uploadProps" :disabled="uploading">
        <p class="ant-upload-drag-icon">
          <UploadOutlined style="font-size: 48px; color: #1890ff" />
        </p>
        <p class="ant-upload-text">拖放文件到此处，或点击选择文件</p>
        <p class="ant-upload-hint">
          支持 PDF、Word (.docx)、TXT、Markdown、CSV 格式，单文件最大 20 MB
        </p>
      </a-upload-dragger>
      <div v-if="uploading" style="margin-top: 16px; text-align: center">
        <a-spin tip="正在处理文档并建立索引..." />
      </div>
    </a-card>

    <!-- Documents table -->
    <a-card
      class="docs-card"
      :bordered="false"
      title="已上传文档"
    >
      <template #extra>
        <a-button
          type="text"
          :icon="h(ReloadOutlined)"
          :loading="loading"
          @click="fetchDocuments"
        >
          刷新
        </a-button>
      </template>

      <a-table
        :dataSource="documents"
        :columns="columns"
        :loading="loading"
        :pagination="{ pageSize: 10, showSizeChanger: true }"
        row-key="doc_id"
        :locale="{ emptyText: '暂无文档，请先上传文件' }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'filename'">
            <div class="filename-cell">
              <component :is="getFileIcon(record.filename)" class="file-icon" />
              <span>{{ record.filename }}</span>
            </div>
          </template>
          <template v-if="column.key === 'action'">
            <a-popconfirm
              :title="`确定删除 &quot;${record.filename}&quot; 吗？`"
              ok-text="删除"
              cancel-text="取消"
              ok-type="danger"
              @confirm="deleteDocument(record)"
            >
              <a-button
                type="text"
                danger
                size="small"
                :icon="h(DeleteOutlined)"
              />
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<style scoped>
.kb-container {
  max-width: 960px;
  margin: 0 auto;
}

.stat-card {
  border-radius: 12px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06) !important;
  transition: box-shadow 0.2s;
}

.stat-card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1) !important;
}

.upload-card,
.docs-card {
  border-radius: 12px !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06) !important;
}

.filename-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  font-size: 16px;
  color: #1890ff;
}
</style>
