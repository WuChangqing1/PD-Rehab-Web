/**
 * Whether the screen is currently the patient's or the doctor's.
 *
 * The shell has to know, because patient mode replaces the workspace chrome
 * (sidebar, header, breadcrumb) for the duration of a task. The *page* knows
 * when a task actually starts -- choosing a patient is still a doctor
 * activity -- so the page raises this flag rather than the route declaring it
 * up front. That distinction matters: hiding the navigation the moment the page
 * opens would strand the doctor before they had done anything.
 *
 * `reset()` exists because a page can be left in ways that skip its unmount
 * handler (a hard navigation, an error boundary). The router calls it on every
 * route change, so the flag can never leak into a page that did not ask for it.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTaskModeStore = defineStore('taskMode', () => {
  const active = ref(false)

  function enter() {
    active.value = true
  }

  function exit() {
    active.value = false
  }

  return { active, enter, exit, reset: exit }
})
