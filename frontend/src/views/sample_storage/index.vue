<template>
  <section class="page" data-module="sample_storage">
    <header class="page-head">
      <div>
        <h2>样品留存工作台</h2>
        <p class="page-desc">围绕留存编号、样品编号、留存位置、留存期限组织日常查看，概览随筛选条件联动。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记留存样品</button>
        <button class="btn" type="button" @click="exportRows">导出样品留存清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article
        v-for="card in overviewCards"
        :key="card.label"
        class="stat-card"
        :class="{ clickable: card.status !== null, active: card.status !== null && card.status === status }"
        @click="card.status !== null && toggleStatus(card.status)"
      >
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ loading ? '—' : card.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model.trim="filters[field.key]" :placeholder="`按${field.label}检索`" />
      </label>
      <label class="filter-item">
        <span>留存状态</span>
        <select v-model="status">
          <option value="">全部状态</option>
          <option v-for="item in statuses" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column" :class="{ 'key-col': keyColumns.includes(column) }">
            {{ column }}
          </th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length + 1" class="empty-state">正在加载样品留存数据…</td>
        </tr>
        <template v-else>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column" :class="{ 'key-col': keyColumns.includes(column) }">
              <span v-if="column === '留存状态'" class="pill" :class="pillClass(row)">
                {{ row.status ?? '—' }}
              </span>
              <template v-else>{{ row[column] ?? '—' }}</template>
            </td>
            <td class="row-actions">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 1" class="empty-state">
              {{ errorMessage ? '数据加载失败，已清空上次结果，请重试' : '当前条件下暂无样品留存记录，可调整筛选或登记留存样品' }}
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条样品留存记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type Summary = { total: number; active: number; by_status: Record<string, number> }

const ENDPOINT = '/api/sample_storage'
const STORAGE_KEY = 'sample_storage_workbench_view'
const columns = ["留存编号", "样品编号", "留存位置", "留存期限", "到期日期", "保管人员", "处理方式", "留存状态"]
const keyColumns = ["留存编号", "样品编号", "留存位置", "留存期限"]
const actions = ["确认处置", "申请延期", "登记处置"]
const statuses = ["留存中", "即将到期", "已处置", "已延期"]
const filterFields = [
  { key: 'retention_no', label: '留存编号' },
  { key: 'sample_no', label: '样品编号' },
  { key: 'location', label: '留存位置' },
  { key: 'period', label: '留存期限' },
]
const PILL_CLASS: Record<string, string> = {
  留存中: 'is-active',
  即将到期: 'is-warning',
  已处置: 'is-done',
  已延期: 'is-extended',
}
const EMPTY_SUMMARY: Summary = { total: 0, active: 0, by_status: {} }

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(true)
const errorMessage = ref('')
const filters = reactive<Record<string, string>>({ retention_no: '', sample_no: '', location: '', period: '' })
const status = ref('')
const summary = ref<Summary>({ ...EMPTY_SUMMARY })

const overviewCards = computed(() => [
  { label: '留存中样品', value: summary.value.active, status: null },
  { label: '留存中', value: summary.value.by_status['留存中'] ?? 0, status: '留存中' },
  { label: '即将到期', value: summary.value.by_status['即将到期'] ?? 0, status: '即将到期' },
  { label: '已处置', value: summary.value.by_status['已处置'] ?? 0, status: '已处置' },
])

function pillClass(row: Row) {
  return PILL_CLASS[String(row.status ?? '')] ?? ''
}

function buildQuery() {
  const query = new URLSearchParams()
  for (const field of filterFields) {
    const value = (filters[field.key] ?? '').trim()
    if (value) {
      query.set(field.key, value)
    }
  }
  if (status.value) {
    query.set('status', status.value)
  }
  return query.toString()
}

function persistView() {
  const snapshot = { filters: { ...filters }, status: status.value }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot))
}

function restoreView() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return
    }
    const saved = JSON.parse(raw) as { filters?: Record<string, string>; status?: string }
    for (const field of filterFields) {
      filters[field.key] = saved.filters?.[field.key] ?? ''
    }
    status.value = saved.status && statuses.includes(saved.status) ? saved.status : ''
  } catch {
    // 本地快照损坏时按全新工作台打开，不沿用旧条件
    window.localStorage.removeItem(STORAGE_KEY)
  }
}

function applyFilters() {
  persistView()
  void reload()
}

function resetFilters() {
  for (const field of filterFields) {
    filters[field.key] = ''
  }
  status.value = ''
  persistView()
  void reload()
}

function toggleStatus(target: string) {
  status.value = status.value === target ? '' : target
  persistView()
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '留存样品登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('样品留存动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '样品留存操作失败'
  }
}

async function reload() {
  loading.value = true
  errorMessage.value = ''
  const query = buildQuery()
  try {
    const [listResponse, summaryResponse] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      request(`${ENDPOINT}/summary?${query}`),
    ])
    if (!listResponse.ok || !summaryResponse.ok) {
      throw new Error('样品留存数据读取失败，请稍后重试')
    }
    const listPayload = await listResponse.json()
    const summaryPayload = await summaryResponse.json()
    rows.value = listPayload.items ?? []
    total.value = listPayload.total ?? rows.value.length
    summary.value = {
      total: summaryPayload.total ?? 0,
      active: summaryPayload.active ?? 0,
      by_status: summaryPayload.by_status ?? {},
    }
  } catch (error) {
    // 失败时清空而不是沿用上次结果，避免误导日常判断
    rows.value = []
    total.value = 0
    summary.value = { ...EMPTY_SUMMARY }
    errorMessage.value = error instanceof Error ? error.message : '样品留存数据读取失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  restoreView()
  void reload()
})
</script>
