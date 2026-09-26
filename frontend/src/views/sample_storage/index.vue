<template>
  <section class="page" data-module="sample_storage">
    <header class="page-head">
      <div>
        <h2>样品留存工作台</h2>
        <p class="page-desc">围绕留存编号、样品编号、留存位置、留存期限组织日常查看，概览随当前条件联动。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记留存样品</button>
        <button class="btn" type="button" @click="exportRows">导出样品留存清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article
        v-for="card in statCards"
        :key="card.label"
        class="stat-card clickable"
        :class="{ active: card.status === activeStatus }"
        @click="selectStatus(card.status)"
      >
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model.trim="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit" :disabled="loading">查询</button>
      <button class="btn ghost" type="button" :disabled="loading" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td class="cell-key">{{ row['留存编号'] ?? '—' }}</td>
          <td class="cell-strong">{{ row['样品编号'] ?? '—' }}</td>
          <td class="cell-strong">{{ row['留存位置'] ?? '—' }}</td>
          <td class="cell-strong">{{ row['留存期限'] ?? '—' }}</td>
          <td>{{ row['到期日期'] ?? '—' }}</td>
          <td>{{ row['保管人员'] ?? '—' }}</td>
          <td>{{ row['处理方式'] ?? '—' }}</td>
          <td>
            <span class="status-pill" :class="statusPillClass(String(row.status ?? ''))">
              {{ row.status ?? '—' }}
            </span>
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
        <tr v-if="loading">
          <td :colspan="columns.length + 1" class="empty-state">正在加载留存样品…</td>
        </tr>
        <tr v-else-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">当前条件下暂无留存样品，可调整条件或登记留存样品</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>
        共 {{ total }} 条样品留存记录
        <template v-if="activeStatus">（当前定位：{{ activeStatus }}）</template>
      </span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/sample_storage'
const STORAGE_KEY = 'sample_storage.workbench'

const columns = ["留存编号", "样品编号", "留存位置", "留存期限", "到期日期", "保管人员", "处理方式", "留存状态"]
const actions = ["确认处置", "申请延期", "登记处置"]
const filterFields = ["留存编号", "样品编号", "留存位置"] as const
const PARAM_MAP: Record<(typeof filterFields)[number], string> = { "留存编号": "keyword", "样品编号": "sample_no", "留存位置": "location" }
const STATUS_ORDER = ["留存中", "即将到期", "已处置", "已延期"]
const CARD_LABELS: Record<string, string> = { "": "全部留存", "留存中": "留存中样品", "即将到期": "即将到期", "已处置": "已处置", "已延期": "已延期" }

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')
const filters = reactive<Record<string, string>>({ "留存编号": "", "样品编号": "", "留存位置": "" })
const activeStatus = ref('')
const grandTotal = ref(0)
const counts = ref<Record<string, number>>({})

const statCards = computed(() =>
  ["", ...STATUS_ORDER].map((status) => ({
    status,
    label: CARD_LABELS[status],
    value: status ? counts.value[status] ?? 0 : grandTotal.value,
  })),
)

function normalizeStatus(value: unknown): string {
  return typeof value === 'string' && STATUS_ORDER.includes(value) ? value : ''
}

function restoreState() {
  // URL 上有条件时以 URL 为准，否则回退到本地缓存，保证再次打开仍能看到刚才的定位
  const query = route.query
  const params = Object.values(PARAM_MAP).concat('status')
  const hasQuery = params.some((key) => typeof query[key] === 'string' && query[key])
  if (hasQuery) {
    for (const field of filterFields) {
      const value = query[PARAM_MAP[field]]
      filters[field] = typeof value === 'string' ? value : ''
    }
    activeStatus.value = normalizeStatus(query.status)
    return
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return
    }
    const saved = JSON.parse(raw) as Record<string, unknown>
    for (const field of filterFields) {
      const value = saved[PARAM_MAP[field]]
      filters[field] = typeof value === 'string' ? value : ''
    }
    activeStatus.value = normalizeStatus(saved.status)
  } catch {
    // 缓存损坏时按默认条件展示
  }
}

function persistState() {
  const query: Record<string, string> = {}
  for (const field of filterFields) {
    const value = filters[field].trim()
    if (value) {
      query[PARAM_MAP[field]] = value
    }
  }
  if (activeStatus.value) {
    query.status = activeStatus.value
  }
  void router.replace({ query }).catch(() => {})
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(query))
  } catch {
    // 隐私模式等场景写不进去就跳过，不影响查看
  }
}

function buildParams(includeStatus: boolean): string {
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = filters[field].trim()
    if (value) {
      params.set(PARAM_MAP[field], value)
    }
  }
  if (includeStatus && activeStatus.value) {
    params.set('status', activeStatus.value)
  }
  return params.toString()
}

function statusPillClass(status: string): string {
  switch (status) {
    case '留存中':
      return 'pill-active'
    case '即将到期':
      return 'pill-warning'
    case '已处置':
      return 'pill-done'
    case '已延期':
      return 'pill-extended'
    default:
      return ''
  }
}

function selectStatus(status: string) {
  activeStatus.value = status
  void reload()
}

function applyFilters() {
  void reload()
}

function resetFilters() {
  for (const field of filterFields) {
    filters[field] = ''
  }
  activeStatus.value = ''
  void reload()
}

function exportRows() {
  const query = buildParams(true)
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
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

let requestSeq = 0

async function reload() {
  const ticket = ++requestSeq
  loading.value = true
  errorMessage.value = ''
  persistState()
  const listQuery = buildParams(true)
  const summaryQuery = buildParams(false) // 概览只跟随检索条件，不含状态筛选，保证各状态卡片分布完整
  try {
    const [listResponse, summaryResponse] = await Promise.all([
      request(`${ENDPOINT}?${listQuery}`),
      request(`${ENDPOINT}/summary?${summaryQuery}`),
    ])
    if (!listResponse.ok || !summaryResponse.ok) {
      throw new Error('留存样品工作台数据读取失败')
    }
    const listPayload = await listResponse.json()
    const summaryPayload = await summaryResponse.json()
    if (ticket !== requestSeq) {
      return // 已有更新的查询，丢弃过期结果
    }
    rows.value = listPayload.items ?? []
    total.value = listPayload.total ?? rows.value.length
    grandTotal.value = summaryPayload.total ?? 0
    counts.value = summaryPayload.counts ?? {}
  } catch (error) {
    if (ticket !== requestSeq) {
      return
    }
    // 失败时清空列表与概览，不沿用上次结果
    rows.value = []
    total.value = 0
    grandTotal.value = 0
    counts.value = {}
    errorMessage.value = error instanceof Error ? error.message : '留存样品工作台数据读取失败'
  } finally {
    if (ticket === requestSeq) {
      loading.value = false
    }
  }
}

onMounted(() => {
  restoreState()
  void reload()
})
</script>

<style scoped>
.stat-card.clickable { cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s; }
.stat-card.clickable:hover { border-color: var(--brand); }
.stat-card.active { border-color: var(--brand); box-shadow: 0 0 0 1px var(--brand); }
.stat-card.active .stat-value { color: var(--brand); }
.cell-key { font-weight: 600; color: var(--brand); }
.cell-strong { font-weight: 600; }
.status-pill { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; background: #eef2f7; color: var(--muted); }
.status-pill.pill-active { background: #e7f6ec; color: #15803d; }
.status-pill.pill-warning { background: #fef3e2; color: #b45309; }
.status-pill.pill-done { background: #eef2f7; color: #475569; }
.status-pill.pill-extended { background: #e8effd; color: #1d4ed8; }
</style>
