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


export async function apiRequest(
  url,
  {
    method = 'GET',
    body,
  } = {},
) {
  const normalizedMethod = method.toUpperCase()

  if (
    ['POST', 'PUT', 'PATCH', 'DELETE']
      .includes(normalizedMethod)
  ) {
    await ensureCsrf()
  }

  const headers = {}

  if (body !== undefined && !(body instanceof FormData)) {
    headers['Content-Type']
      = 'application/json; charset=utf-8'
  }

  const csrfToken = getCookie(
    'csrftoken'
  )

  if (
    csrfToken
    && ['POST', 'PUT', 'PATCH', 'DELETE']
      .includes(normalizedMethod)
  ) {
    headers['X-CSRFToken']
      = csrfToken
  }

  const response = await fetch(
    url,
    {
      method: normalizedMethod,
      headers,
      credentials: 'include',
      body:
        body === undefined
          ? undefined
          : body instanceof FormData ? body : JSON.stringify(body),
    }
  )

  return parseResponse(
    response
  )
}


export async function fetchPosts(
  category = '',
  search = '',
) {
  const params = new URLSearchParams()
  if(category) params.set('category',category)
  if(search.trim()) params.set('q',search.trim())
  const query = params.size ? `?${params}` : ''

  const payload = await apiRequest(
    `/api/social/posts/${query}`
  )

  return payload.posts || []
}


export async function createPost(
  data,
) {
  const payload = await apiRequest(
    '/api/social/posts/',
    {
      method: 'POST',
      body: data,
    }
  )

  return payload.post
}


export async function togglePostLike(
  postId,
) {
  return apiRequest(
    `/api/social/posts/${postId}/like/`,
    {
      method: 'POST',
      body: {},
    }
  )
}


export async function togglePostSave(
  postId,
) {
  return apiRequest(
    `/api/social/posts/${postId}/save/`,
    {
      method: 'POST',
      body: {},
    }
  )
}


export async function fetchComments(
  postId,
) {
  const payload = await apiRequest(
    `/api/social/posts/${postId}/comments/`
  )

  return payload.comments || []
}


export async function createComment(
  postId,
  content,
) {
  const payload = await apiRequest(
    `/api/social/posts/${postId}/comments/`,
    {
      method: 'POST',
      body: {
        content,
      },
    }
  )

  return payload.comment
}



export async function fetchSavedPosts() {
  const payload = await apiRequest(
    '/api/social/saved/'
  )

  return payload.posts || []
}
