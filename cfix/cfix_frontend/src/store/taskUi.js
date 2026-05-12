import { defineStore } from 'pinia'


export const useTaskUiStore = defineStore('taskUi', {
  state: () => ({
    pendingActions: {}
  }),
  getters: {
    taskActionById: state => taskId => {
      const id = Number(taskId || 0)
      if (!id) return ''
      return state.pendingActions[String(id)]?.action || ''
    },
    taskStatusById() {
      return (taskId, baseStatus = 'draft') => {
        const action = this.taskActionById(taskId)
        return action || baseStatus || 'draft'
      }
    }
  },
  actions: {
    setTaskAction(taskId, action) {
      const id = Number(taskId || 0)
      const nextAction = String(action || '').trim()
      if (!id || !nextAction) return
      this.pendingActions = {
        ...this.pendingActions,
        [String(id)]: {
          action: nextAction,
          updatedAt: Date.now()
        }
      }
    },
    clearTaskAction(taskId, expectedAction = '') {
      const id = Number(taskId || 0)
      if (!id) return
      const key = String(id)
      const current = this.pendingActions[key]
      if (!current) return
      if (expectedAction && current.action !== expectedAction) return
      const next = { ...this.pendingActions }
      delete next[key]
      this.pendingActions = next
    },
    clearAll() {
      this.pendingActions = {}
    }
  }
})