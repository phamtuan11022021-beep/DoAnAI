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


export async function fetchCareerQuestions() {
  const response = await fetch(
    '/api/career/questions/',
    {
      method: 'GET',
      credentials: 'include',
    }
  )

  return parseResponse(
    response
  )
}


export async function submitCareerAssessment(
  answers,
) {
  await ensureCsrf()

  const csrfToken = getCookie(
    'csrftoken'
  )

  const response = await fetch(
    '/api/career/submit/',
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
        answers,
      }),
    }
  )

  return parseResponse(
    response
  )
}


export async function fetchCareerHistory() {
  const response = await fetch(
    '/api/career/history/',
    {
      method: 'GET',
      credentials: 'include',
    }
  )

  return parseResponse(
    response
  )
}
