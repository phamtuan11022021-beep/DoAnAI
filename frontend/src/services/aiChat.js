import {
  ensureCsrf,
} from './auth'


function getCookie(name) {
  const cookies = document.cookie
    ? document.cookie.split(';')
    : []

  for (const item of cookies) {
    const cookie = item.trim()

    if (cookie.startsWith(`${name}=`)) {
      return decodeURIComponent(
        cookie.slice(name.length + 1)
      )
    }
  }

  return ''
}


async function parseResponse(response) {
  let payload = {}

  try {
    payload = await response.json()
  } catch {
    payload = {}
  }

  if (!response.ok) {
    throw new Error(
      payload.error
      || `HTTP ${response.status}`
    )
  }

  return payload
}


export async function sendAIChatMessage({
  message,
  conversationId,
  uiContext,
}) {
  await ensureCsrf()

  const csrfToken = getCookie(
    'csrftoken'
  )

  const response = await fetch(
    '/api/ai-chat/chat/',
    {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type':
          'application/json; charset=utf-8',
        ...(csrfToken
          ? {
              'X-CSRFToken':
                csrfToken,
            }
          : {}),
      },
      body: JSON.stringify({
        message,
        conversation_id:
          conversationId || null,
        ui_context:
          uiContext || {},
      }),
    }
  )

  return parseResponse(
    response
  )
}


export async function fetchAIChatHistory(
  conversationId = '',
) {
  const query = conversationId
    ? `?conversation_id=${encodeURIComponent(conversationId)}`
    : ''

  const response = await fetch(
    `/api/ai-chat/history/${query}`,
    {
      method: 'GET',
      credentials: 'include',
    }
  )

  return parseResponse(
    response
  )
}


export async function createAIChatConversation() {
  await ensureCsrf()

  const csrfToken = getCookie(
    'csrftoken'
  )

  const response = await fetch(
    '/api/ai-chat/new/',
    {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type':
          'application/json; charset=utf-8',
        ...(csrfToken
          ? {
              'X-CSRFToken':
                csrfToken,
            }
          : {}),
      },
      body: JSON.stringify({}),
    }
  )

  return parseResponse(
    response
  )
}