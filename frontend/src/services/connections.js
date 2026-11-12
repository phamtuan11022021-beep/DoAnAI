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


export async function fetchConnectionSuggestions(
  limit = 8,
) {
  const response = await fetch(
    `/api/connections/suggestions/?limit=${encodeURIComponent(limit)}`,
    {
      method: 'GET',
      credentials: 'include',
    }
  )

  const payload = await parseResponse(
    response
  )

  return payload.users || []
}


export async function fetchFollowing() {
  const response = await fetch(
    '/api/connections/following/',
    {
      method: 'GET',
      credentials: 'include',
    }
  )

  const payload = await parseResponse(
    response
  )

  return payload.users || []
}


export async function toggleFollow(
  userId,
) {
  await ensureCsrf()

  const csrfToken = getCookie(
    'csrftoken'
  )

  const response = await fetch(
    `/api/connections/follow/${userId}/`,
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
