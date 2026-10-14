import { ref } from 'vue'
import { getUnreadNotificationCount } from '../../api/notificationService.js'

// One count shared by the bell in the shell and the notifications page, so
// reading something in either place updates the badge straight away (SPM-94 AC1).
export const unreadCount = ref(0)

export async function refreshUnreadCount() {
  try {
    const { data } = await getUnreadNotificationCount()
    unreadCount.value = data.unreadCount
  } catch {
    // Best effort - the badge just won't update this time.
  }
}
