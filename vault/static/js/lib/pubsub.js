
const DEBUG = false

export const TOPICS = new Set([
  "API_REQUEST",
  "API_RESPONSE",
  "CHANGE_DIRECTORY",
  "CHANGE_DIRECTORY_REQUEST",
  "DETAILS_PANEL_CLOSED",
  "DETAILS_PANEL_OPEN",
  "FILE_CONTEXT_MENU_ITEM_SELECTED",
  "FILE_ROW_SELECTED",
  "HIDE_DETAILS_PANEL",
  "NODES_DELETE_REQUEST",
  "NODES_DELETE_RESPONSE",
  "NODE_RENAME_REQUEST",
  "NODE_RENAME_RESPONSE",
  "OPEN_FILE_REQUEST",
  "SHOW_DETAILS_PANEL",
])

const topicSubscribersMap = new Map(
  Array.from(TOPICS).map(topic => [ topic, [] ])
)

function assertValidTopic (topic) {
  if (!TOPICS.has(topic)) {
    throw new Error(`Undefined topic: ${topic}`)
  }
}

export function subscribe (topic, func) {
  /* Subscribe func to the specified topic.
   */
  assertValidTopic(topic)
  const subscribers = topicSubscribersMap.get(topic)
  // Do not subscribe func more than once.
  if (!subscribers.includes(func)) {
    subscribers.push(func)
  }
}

export function unsubscribe (topic, func) {
  /* Unsubscribe func from the specified topic.
   */
  assertValidTopic(topic)
  topicSubscribersMap.set(
    topic,
    topicSubscribersMap.get(topic).filter(f => f !== func)
  )
}

// Define a monotonically increasing message ID integer.
let messageId = 0

export async function publish (topic, message) {
  /* Publish the specified message to all topic subscribers.
   */
  assertValidTopic(topic)
  messageId += 1
  if (DEBUG) {
    console.debug(
      `Publishing to ${topicSubscribersMap.get(topic).length} subscribers ` +
       `on topic "${topic}" with message (id:${messageId}): ${JSON.stringify(message)}`
    )
  }
  await Promise.all(
    topicSubscribersMap.get(topic).map(func =>
      new Promise(resolve => resolve(func(message, messageId)))
    )
  )
}