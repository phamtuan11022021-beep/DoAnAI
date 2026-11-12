function getCookie(name) {
  const cookies = document.cookie ? document.cookie.split(';') : []

  for (const item of cookies) {
    const cookie = item.trim()
    if (cookie.startsWith(`${name}=`)) {
      return decodeURIComponent(cookie.slice(name.length + 1))
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
    const detail = Array.isArray(payload.details)
      ? ` ${payload.details.join(' ')}`
      : ''

    throw new Error(
      `${payload.error || `HTTP ${response.status}`}${detail}`
    )
  }

  return payload
}


export async function ensureCsrf() {
  const response = await fetch('/api/auth/csrf/', {
    method: 'GET',
    credentials: 'include',
  })

  return parseResponse(response)
}


async function apiRequest(url, options = {}) {
  const method = String(options.method || 'GET').toUpperCase()

  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    await ensureCsrf()
  }

  const headers = {
    ...(options.headers || {}),
  }

  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json; charset=utf-8'
  }

  const csrfToken = getCookie('csrftoken')

  if (csrfToken && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    headers['X-CSRFToken'] = csrfToken
  }

  const response = await fetch(url, {
    ...options,
    method,
    headers,
    credentials: 'include',
  })

  return parseResponse(response)
}


export async function getMe() {
  const response = await fetch('/api/auth/me/', {
    method: 'GET',
    credentials: 'include',
  })

  if (response.status === 401) {
    return null
  }

  const payload = await parseResponse(response)
  return payload.user
}


export async function loginAccount({ identifier, email, password }) {
  const payload = await apiRequest('/api/auth/login/', {
    method: 'POST',
    body: JSON.stringify({
      identifier: identifier ?? email,
      password,
    }),
  })

  return payload.user
}


export async function registerAccount({
  name,
  email,
  password,
  passwordConfirm,
}) {
  const payload = await apiRequest('/api/auth/register/', {
    method: 'POST',
    body: JSON.stringify({
      name,
      email,
      password,
      password_confirm: passwordConfirm,
    }),
  })

  return payload.user
}


export async function logoutAccount() {
  await apiRequest('/api/auth/logout/', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}


export async function updateMyProfile(data) {
  const payload = await apiRequest('/api/auth/me/', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })

  return payload.user
}

export async function uploadAvatar(file) {
  const body = new FormData()
  body.append('avatar', file)
  const payload = await apiRequest('/api/auth/avatar/', { method: 'POST', body })
  return payload.user
}
