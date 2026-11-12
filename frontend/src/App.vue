<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  Activity, Bell, Bookmark, BookOpen, Bot, Building2, Check, ChevronDown, CircleUserRound,
  Clock3, FileText, GraduationCap, Hash, Image as ImageIcon, LayoutDashboard,
  Lightbulb, MapPin, Menu, MessageCircle, MessagesSquare, Moon, MoreHorizontal,
  Paperclip, Plus, Search, Send, Settings2, Share2, ShieldCheck, Sparkles, Star,
  Sun, Target, ThumbsUp, TrendingUp, Users, X, Zap
} from 'lucide-vue-next'

import AuthModal from './components/AuthModal.vue'
import ProfileModal from './components/ProfileModal.vue'
import CommunityInbox from './components/CommunityInbox.vue'
import PostAttachments from './components/PostAttachments.vue'
import CampusHero from './components/CampusHero.vue'
import { apiRequest, fetchComments } from './services/social'
import {
  getMe,
  logoutAccount,
} from './services/auth'

import {
  createComment,
  createPost,
  fetchPosts,
  fetchSavedPosts,
  togglePostLike,
  togglePostSave,
} from './services/social'

import {
  fetchConnectionSuggestions,
  toggleFollow,
} from './services/connections'

import {
  fetchCareerHistory,
  fetchCareerQuestions,
  submitCareerAssessment,
} from './services/career'

import {
  fetchSavedUniversities,
  toggleSavedUniversity,
} from './services/catalog'

import {
  createAIChatConversation,
  fetchAIChatHistory,
  sendAIChatMessage,
} from './services/aiChat'

const activeTab = ref('advisor')
const communityInbox = ref(null)
const toast = ref('')
const postImages = ref([])
const imageInput = ref(null)
const pollEnabled = ref(false)
const pollDraft = ref(['', ''])
const editingPost = ref(null)
const editingContent = ref('')
const postMenu = ref(null)
const deleteCandidate = ref(null)
const composerError = ref('')
const pendingPost = new URLSearchParams(window.location.search).get('post')
function notify(text) { toast.value = text; setTimeout(() => { toast.value = '' }, 4500) }
function chooseImages(event) {
  composerError.value = ''
  const files = Array.from(event.target.files || [])
  if (files.length + postImages.value.length > 4) { composerError.value='Mỗi bài tối đa 4 ảnh.'; return }
  for (const file of files) {
    if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 5*1024*1024) {
      composerError.value='Chọn ảnh JPG, PNG hoặc WebP, tối đa 5 MB mỗi ảnh.'; continue
    }
    postImages.value.push({file, url:URL.createObjectURL(file)})
  }
  event.target.value=''
}
function removeImage(index) { URL.revokeObjectURL(postImages.value[index].url); postImages.value.splice(index,1) }
function clearImages() { postImages.value.forEach(i => URL.revokeObjectURL(i.url)); postImages.value=[] }
async function openSharedPost(id) {
  try {
    const data=await apiRequest(`/api/social/posts/?post=${encodeURIComponent(id)}`)
    activeTab.value='social'; await nextTick()
    posts.value=data.posts.map(normalizeSocialPost)
    if(!posts.value.length) notify('Bài viết không còn tồn tại.')
    history.replaceState(null,'',`?post=${encodeURIComponent(id)}`)
    window.scrollTo({top:0,behavior:'smooth'})
  } catch(e) { notify(e.message) }
}
async function editPost() {
  if(!editingContent.value.trim()) return
  try {
    const data=await apiRequest(`/api/social/posts/${editingPost.value.id}/`,{method:'PATCH',body:{content:editingContent.value}})
    const updated=normalizeSocialPost(data.post)
    posts.value=posts.value.map(p=>p.id===updated.id?updated:p)
    editingPost.value=null; notify('Đã cập nhật bài viết.')
  } catch(e) { notify(e.message) }
}
async function deletePost() {
  try {
    await apiRequest(`/api/social/posts/${deleteCandidate.value.id}/`,{method:'DELETE'})
    posts.value=posts.value.filter(p=>p.id!==deleteCandidate.value.id)
    deleteCandidate.value=null; notify('Đã xóa bài viết của bạn.')
  } catch(e) { notify(e.message) }
}
async function showAllComments(post) {
  try {
    const data=await fetchComments(post.id)
    post.topComments=data.map(c=>({id:c.id,author:c.author.name,initials:c.author.initials,avatar:c.author.avatar_url,content:c.content,time:c.time}))
    commentOpen[post.id]=true
  } catch(e) { notify(e.message) }
}
const darkMode = ref(localStorage.getItem('uniconnect-theme') === 'dark')
const mobileMenu = ref(false)
const searchOpen = ref(false)
const searchQuery = ref('')
const notificationOpen = ref(false)
const messageOpen = ref(false)
const profileOpen = ref(false)
const universityModal = ref(null)
const creatingPost = ref(false)
const newPost = ref('')
const newPostTag = ref('#ChonTruong2027')
const newPostCategory = ref('general')
const feedFilter = ref('Dành cho bạn')
const socialLoading = ref(false)
const socialError = ref('')
const feedSearch = ref('')
const socialActionBusy = ref({})
const commentDrafts = reactive({})
const commentOpen = reactive({})
const compareList = ref([])
const compareDetails = ref({})
const compareLoading = ref(false)
const compareError = ref('')
const compareMajorQuery = ref('')
const compareAddKey = ref('')

const mentorSuggestions = ref([])
const mentorLoading = ref(false)
const mentorError = ref('')
const connectionBusy = ref({})

const careerQuestions = ref([])
const careerDimensions = ref({})
const careerScale = ref({})
const careerIndex = ref(0)
const careerAnswers = reactive({})
const careerLoading = ref(false)
const careerSubmitting = ref(false)
const careerError = ref('')
const careerResult = ref(null)
const careerHistory = ref([])
const careerDisclaimer = ref('')

const chatInput = ref('')
const chatLoading = ref(false)
const chatBox = ref(null)
const chatError = ref('')
const chatConversationId = ref(
  sessionStorage.getItem('uniconnect-ai-chat-id') || ''
)
const apiLoading = ref(false)
const apiError = ref('')
const hasSubmitted = ref(false)
const aiResults = ref([])
const lastModelInfo = ref(null)
const lastAdvisorReason = ref('')
const advisorResultScope = ref('STRICT')
const strictCity = ref('')
const advisorDiagnostics = ref(null)
const otherAdmissionMethods = ref([])
const advisorAlternatives = ref({
  same_city_unverified_combination: [],
  nationwide_verified: [],
  same_city_historical: [],
  related_major_name: [],
})

const catalogSchools = ref([])
const catalogLoading = ref(false)
const catalogError = ref('')
const schoolDetail = ref(null)
const schoolDetailLoading = ref(false)
const schoolProgramQuery = ref('')

const savedSection = ref('schools')
const savedUniversities = ref([])
const savedUniversitiesLoading = ref(false)
const savedUniversitiesError = ref('')
const savingUniversity = ref({})

let advisorDebounce = null
let advisorRequest = 0

const currentUser = ref(null)
const authOpen = ref(false)
const authMode = ref('login')
const profileEditorOpen = ref(false)

const profile = computed(() => {
  const name = currentUser.value?.name || 'Khách'
  const words = name.split(/\s+/).filter(Boolean)
  const initials = words.length >= 2
    ? `${words[0][0]}${words[words.length - 1][0]}`.toUpperCase()
    : name.slice(0, 2).toUpperCase()

  return {
    name,
    initials,
  }
})

const form = reactive({
  score: 28,
  combination: 'A01',
  major: 'Công nghệ thông tin',
  majorCode: '',
  city: 'Đà Nẵng',
  top: 20,
})

const feeFilter = ref('Tất cả')
const discoveryCity = ref('Tất cả')
const combinationOptions = ['A00', 'A01', 'B00', 'C00', 'D01', 'D07']
const cityOptions = [
  'Đà Nẵng','Hà Nội','Hồ Chí Minh','Phú Thọ','Thái Nguyên','Hải Phòng',
  'Quảng Ninh','Ninh Bình','Hưng Yên','Đồng Tháp','Vĩnh Long','Hà Tĩnh','Huế','Đắk Lắk'
]

const navItems = [
  { id:'advisor', label:'AI Advisor', note:'Phân tích & tư vấn', icon:Bot },
  { id:'social', label:'Feed cộng đồng', note:'Hỏi đáp & chia sẻ', icon:LayoutDashboard },
  { id:'universities', label:'Khám phá trường', note:'Cơ sở dữ liệu tuyển sinh', icon:Building2 },
  { id:'compare', label:'So sánh trường', note:'Đối chiếu lựa chọn', icon:Target },
  { id:'quiz', label:'Trắc nghiệm hướng nghiệp', note:'Holland RIASEC', icon:Lightbulb },
  { id:'saved', label:'Đã lưu', note:'Trường & bài viết', icon:Bookmark },
]

const campusShortcuts = [
  { id:'social', label:'Cộng đồng', icon:Users },
  { id:'advisor', label:'Chọn ngành', icon:GraduationCap },
  { id:'universities', label:'Trường đại học', icon:Building2 },
  { id:'compare', label:'So sánh trường', icon:Target },
  { id:'quiz', label:'Hướng nghiệp', icon:Lightbulb },
  { id:'saved', label:'Đã lưu', icon:Bookmark },
]

async function searchFromCampus(query) {
  if(!query) { searchOpen.value=true; return }
  const school=catalogSchools.value.find(s=>normalize(s.name).includes(normalize(query)))
  if(school) { await openUniversity(school); return }
  form.major=query; form.majorCode=''; setTab('advisor'); await nextTick(); await runAdvisor()
}

const quickPrompts = [
  'Với 24 điểm A01 ngành CNTT ở Đà Nẵng nên chọn trường nào?',
  'Điểm CNTT của Đại học Kiến trúc Đà Nẵng từ 2023 đến 2026',
  'Giải thích sai số và mức An toàn / Phù hợp / Thử sức',
]

const defaultChatGreeting = {
  id: 'local-greeting',
  role: 'assistant',
  text: 'Chào bạn! Mình là UniConnect AI, trợ lý tư vấn tuyển sinh. Mình có thể tư vấn chọn trường, tra điểm chuẩn và giải thích kết quả dự đoán từ dữ liệu của dự án.',
  intent: 'greeting',
  cards: [],
  suggestions: quickPrompts.slice(0,2),
}

const chatMessages = ref([
  defaultChatGreeting
])

const trends = computed(() => [...catalogSchools.value]
  .filter(school=>!form.city || school.city===form.city)
  .sort((a,b)=>(b.program_count||0)-(a.program_count||0)).slice(0,5)
  .map((school,index)=>({...school,rank:index+1,searches:`${school.program_count} chương trình có dữ liệu`,delta:'Xem trường'})))

const hashtags = ['#ChonTruong2027','#ReviewDaiHoc','#KhoiA01','#CNTT','#TuVanNguyenVong']

const mockUniversities = ref([])


const posts = ref([])


const feedTabs = ['Dành cho bạn','Review trường','Kinh nghiệm ôn thi','Hỏi đáp AI']

const feedCategoryMap = {
  'Dành cho bạn': '',
  'Review trường': 'review',
  'Kinh nghiệm ôn thi': 'experience',
  'Hỏi đáp AI': 'ai',
}

const postCategoryOptions = [
  { value: 'general', label: 'Dành cho bạn' },
  { value: 'review', label: 'Review trường' },
  { value: 'experience', label: 'Kinh nghiệm ôn thi' },
  { value: 'ai', label: 'Hỏi đáp AI' },
]

const searchIndex = computed(() => [
  ...catalogSchools.value.map(u => ({ type:'Trường', title:u.name, subtitle:`${u.city || 'Chưa có metadata vị trí'} • ${u.field}`, action:() => openUniversity(u) })),
  ...posts.value.map(p => ({ type:'Bài viết', title:p.content.slice(0,72)+(p.content.length>72?'…':''), subtitle:`${p.author} • ${p.time}`, action:() => { searchOpen.value=false; openSharedPost(p.id) } })),
  ...hashtags.map(tag => ({ type:'Hashtag', title:tag, subtitle:'Chủ đề nổi bật trong cộng đồng', action:() => searchFeed(tag) }))
])

const searchResults = computed(() => {
  const q = normalize(searchQuery.value)
  if (!q) return searchIndex.value.slice(0,8)
  return searchIndex.value.filter(item => normalize(`${item.title} ${item.subtitle} ${item.type}`).includes(q)).slice(0,10)
})

const filteredUniversities = computed(() => {
  const q = normalize(searchQuery.value)
  return catalogSchools.value.filter(u => {
    const cityOk = discoveryCity.value === 'Tất cả' || !discoveryCity.value || u.city === discoveryCity.value
    const searchOk = !q || normalize(`${u.name} ${u.city} ${u.field}`).includes(q)
    return cityOk && searchOk
  })
})

const filteredSchoolPrograms = computed(() => {
  const programs = schoolDetail.value?.programs || []
  const q = normalize(schoolProgramQuery.value)

  if (!q) return programs

  return programs.filter(program =>
    normalize(`${program.major_code} ${program.major_name}`).includes(q)
  )
})

const compareAvailableSchools = computed(() => {
  const selected = new Set(
    compareList.value.map(item => item.id)
  )

  return catalogSchools.value.filter(
    school => !selected.has(school.id)
  )
})

const compareProgramResults = computed(() => {
  const q = normalize(compareMajorQuery.value)

  return compareList.value.map(school => {
    const detail = compareDetails.value[school.id]
    const programs = detail?.programs || []

    const matched = q
      ? programs.filter(program =>
          normalize(
            `${program.major_code} ${program.major_name}`
          ).includes(q)
        ).slice(0, 8)
      : []

    return {
      school,
      detail,
      programs: matched,
    }
  })
})

const careerCurrentQuestion = computed(() =>
  careerQuestions.value[careerIndex.value] || null
)

const careerAnsweredCount = computed(() =>
  Object.keys(careerAnswers).filter(
    key => careerAnswers[key] !== undefined
  ).length
)

const careerProgress = computed(() => {
  if(!careerQuestions.value.length) return 0
  return Math.round(
    careerAnsweredCount.value
    / careerQuestions.value.length
    * 100
  )
})

const quickChips = computed(() => [
  `Khối thi: ${form.combination}`,
  `Điểm: ${Number(form.score).toFixed(1)}`,
  `Tỉnh/Thành: ${form.city || 'Tất cả'}`,
])

const recommendationSummary = computed(() => {
  const counts = {'AN TOÀN':0,'PHÙ HỢP':0,'THỬ SỨC':0,'RỦI RO CAO':0}
  aiResults.value.forEach(r => { if (counts[r.recommendation_level] !== undefined) counts[r.recommendation_level]++ })
  return counts
})


const advisorAlternativeCount = computed(() =>
  Object.values(advisorAlternatives.value || {})
    .reduce(
      (sum, rows) => sum + (Array.isArray(rows) ? rows.length : 0),
      0
    )
)

const advisorCombinationSuggestions = computed(() =>
  advisorDiagnostics.value?.available_combinations || []
)

const countdown = reactive({ days:'--', hours:'--', minutes:'--', seconds:'--' })
let countdownTimer = null
const demoCountdownTarget = new Date('2027-06-25T07:00:00+07:00')

function normalize(value) {
  return String(value||'').normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase().trim()
}
function updateCountdown() {
  const diff = demoCountdownTarget.getTime()-Date.now()
  if (diff <= 0) return Object.assign(countdown,{days:'0',hours:'00',minutes:'00',seconds:'00'})
  countdown.days = String(Math.floor(diff/86400000))
  countdown.hours = String(Math.floor((diff%86400000)/3600000)).padStart(2,'0')
  countdown.minutes = String(Math.floor((diff%3600000)/60000)).padStart(2,'0')
  countdown.seconds = String(Math.floor((diff%60000)/1000)).padStart(2,'0')
}
function setTheme() {
  document.documentElement.classList.toggle('dark',darkMode.value)
  localStorage.setItem('uniconnect-theme',darkMode.value?'dark':'light')
}
function toggleDark(){ darkMode.value=!darkMode.value; setTheme() }
function setTab(id){
  activeTab.value = ['advisor','social','universities','compare','quiz','saved'].includes(id) ? id : 'universities'
  mobileMenu.value=false
  window.scrollTo({top:0,behavior:'smooth'})
}
function schoolShort(name){
  const ignored = new Set(['trường','đh','đại','học','hv','học','viện','và','-'])
  const words = String(name || '')
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .filter(word => !ignored.has(word.toLowerCase()))

  return (words.slice(0,3).map(word => word[0]).join('') || 'UNI').toUpperCase()
}

function schoolAccent(index){
  const accents = [
    'linear-gradient(135deg,#4F46E5,#8B5CF6)',
    'linear-gradient(135deg,#0284C7,#4F46E5)',
    'linear-gradient(135deg,#059669,#0EA5E9)',
    'linear-gradient(135deg,#7C3AED,#DB2777)',
    'linear-gradient(135deg,#0EA5E9,#14B8A6)',
    'linear-gradient(135deg,#E11D48,#7C3AED)',
  ]
  return accents[index % accents.length]
}

async function loadCatalogSchools(){
  catalogLoading.value = true
  catalogError.value = ''

  try{
    const response = await fetch('/api/catalog/schools/?limit=250')
    const payload = await response.json()

    if(!response.ok || !payload.success){
      throw new Error(payload.error || 'Không tải được danh sách trường.')
    }

    catalogSchools.value = (payload.schools || []).map((school,index) => ({
      id: school.university_key,
      university_key: school.university_key,
      name: school.university_name,
      short: schoolShort(school.university_name),
      city: school.city || '',
      address: school.address || '',
      rating: null,
      field: `${school.program_count} ngành • ${school.year_count}/4 năm dữ liệu`,
      fee: 'Chưa có dữ liệu học phí',
      verified: Boolean(school.location_verified),
      available_years: school.available_years || [],
      program_count: school.program_count,
      year_count: school.year_count,
      score_min: school.score_min,
      score_max: school.score_max,
      saved: Boolean(school.saved_by_me),
      accent: schoolAccent(index),
    }))

    const savedCompareKeys = JSON.parse(
      localStorage.getItem('uniconnect-compare-schools') || '[]'
    )

    compareList.value = savedCompareKeys
      .map(key => catalogSchools.value.find(school => school.id === key))
      .filter(Boolean)
      .slice(0, 3)
  }catch(error){
    catalogSchools.value = []
    catalogError.value = error.message || 'Không tải được dữ liệu trường.'
  }finally{
    catalogLoading.value = false
  }
}

function mapSavedUniversityRecord(school,index=0){
  return {
    id: school.university_key,
    university_key: school.university_key,
    name: school.university_name,
    short: schoolShort(school.university_name),
    city: school.city || '',
    address: school.address || '',
    field: `${school.program_count} ngành • ${school.year_count}/4 năm dữ liệu`,
    verified: Boolean(school.location_verified),
    available_years: school.available_years || [],
    program_count: school.program_count,
    year_count: school.year_count,
    score_min: school.score_min,
    score_max: school.score_max,
    saved: true,
    saved_at: school.saved_at || '',
    accent: schoolAccent(index),
  }
}

function resolveCatalogSchool(candidate){
  if(!candidate) return null

  const key = candidate.university_key || candidate.id || ''

  if(key){
    const byKey = catalogSchools.value.find(
      school => school.university_key === key
    )
    if(byKey) return byKey
  }

  const name = candidate.name
    || candidate.university_name
    || ''

  if(!name) return null

  const normalized = normalize(
    displayUniversityName(name)
  )

  return catalogSchools.value.find(
    school =>
      normalize(
        displayUniversityName(school.name)
      ) === normalized
  ) || null
}

function isUniversitySaved(candidate){
  const school = resolveCatalogSchool(candidate)
  return Boolean(school?.saved)
}

async function loadSavedUniversities(){
  if(!currentUser.value){
    savedUniversities.value = []
    savedUniversitiesError.value = ''
    return
  }

  savedUniversitiesLoading.value = true
  savedUniversitiesError.value = ''

  try{
    const rows = await fetchSavedUniversities()

    savedUniversities.value = rows.map(
      (school,index) => mapSavedUniversityRecord(
        school,
        index
      )
    )

    const savedKeys = new Set(
      savedUniversities.value.map(
        school => school.university_key
      )
    )

    catalogSchools.value.forEach(school => {
      school.saved = savedKeys.has(
        school.university_key
      )
    })
  }catch(error){
    savedUniversities.value = []
    savedUniversitiesError.value =
      error.message || 'Không tải được trường đã lưu.'
  }finally{
    savedUniversitiesLoading.value = false
  }
}

async function toggleUniversitySave(candidate){
  if(!currentUser.value){
    openAuth('login')
    return
  }

  const school = resolveCatalogSchool(candidate)

  if(!school){
    apiError.value =
      'Không ánh xạ được trường này với catalog sạch hiện tại.'
    return
  }

  savingUniversity.value = {
    ...savingUniversity.value,
    [school.university_key]: true,
  }

  savedUniversitiesError.value = ''

  try{
    const payload = await toggleSavedUniversity(
      school.university_key
    )

    school.saved = Boolean(
      payload.saved
    )

    if(universityModal.value){
      const modalSchool = resolveCatalogSchool(
        universityModal.value
      )
      if(
        modalSchool
        && modalSchool.university_key === school.university_key
      ){
        universityModal.value = {
          ...universityModal.value,
          saved: school.saved,
        }
      }
    }

    await loadSavedUniversities()
  }catch(error){
    savedUniversitiesError.value =
      error.message || 'Không thể cập nhật trường đã lưu.'
  }finally{
    savingUniversity.value = {
      ...savingUniversity.value,
      [school.university_key]: false,
    }
  }
}

async function saveAdvisorUniversity(result){
  const school = resolveCatalogSchool({
    university_name:
      displayUniversityName(
        result.university_name
      )
  })

  if(!school){
    apiError.value =
      'Trường từ kết quả AI chưa ánh xạ được với catalog sạch để lưu.'
    return
  }

  await toggleUniversitySave(
    school
  )
}

async function openUniversity(u){
  searchOpen.value = false
  schoolProgramQuery.value = ''
  schoolDetail.value = null

  let school = u
  let universityKey = u?.university_key || u?.id || ''

  if(!universityKey && u?.name){
    const found = catalogSchools.value.find(item =>
      normalize(item.name) === normalize(u.name)
    )
    if(found){
      school = found
      universityKey = found.university_key
    }
  }

  universityModal.value = school

  if(!universityKey){
    return
  }

  schoolDetailLoading.value = true

  try{
    const response = await fetch(
      `/api/catalog/school-detail/?university_key=${encodeURIComponent(universityKey)}`
    )
    const payload = await response.json()

    if(!response.ok || !payload.success){
      throw new Error(payload.error || 'Không tải được lịch sử điểm chuẩn.')
    }

    schoolDetail.value = payload.school

    const resolved = resolveCatalogSchool({
      university_key: payload.school.university_key,
      university_name: payload.school.university_name,
    })

    if(resolved){
      resolved.saved = Boolean(
        payload.school.saved_by_me
      )

      universityModal.value = {
        ...universityModal.value,
        university_key: resolved.university_key,
        id: resolved.id,
        saved: resolved.saved,
      }
    }
  }catch(error){
    schoolDetail.value = {
      error: error.message || 'Không tải được lịch sử điểm chuẩn.',
      programs: [],
    }
  }finally{
    schoolDetailLoading.value = false
  }
}
function persistCompare(){
  localStorage.setItem(
    'uniconnect-compare-schools',
    JSON.stringify(
      compareList.value.map(item => item.id)
    )
  )
}

async function fetchSchoolDetailForCompare(school){
  const response = await fetch(
    `/api/catalog/school-detail/?university_key=${encodeURIComponent(school.university_key || school.id)}`
  )
  const payload = await response.json()

  if(!response.ok || !payload.success){
    throw new Error(
      payload.error
      || `Không tải được dữ liệu ${school.name}.`
    )
  }

  return payload.school
}

async function loadCompareDetails(){
  compareError.value = ''

  if(compareList.value.length === 0){
    compareDetails.value = {}
    return
  }

  compareLoading.value = true

  try{
    const entries = await Promise.all(
      compareList.value.map(async school => {
        const detail = await fetchSchoolDetailForCompare(school)
        return [school.id, detail]
      })
    )

    compareDetails.value = Object.fromEntries(entries)
  }catch(error){
    compareError.value = error.message || 'Không tải được dữ liệu so sánh.'
  }finally{
    compareLoading.value = false
  }
}

async function toggleCompare(u){
  const exists = compareList.value.some(x => x.id === u.id)

  if(exists){
    compareList.value = compareList.value.filter(x => x.id !== u.id)
    const nextDetails = { ...compareDetails.value }
    delete nextDetails[u.id]
    compareDetails.value = nextDetails
  }else if(compareList.value.length < 3){
    compareList.value = [...compareList.value, u]
  }

  persistCompare()

  if(activeTab.value === 'compare'){
    await loadCompareDetails()
  }
}

async function addCompareSchool(){
  const school = catalogSchools.value.find(
    item => item.id === compareAddKey.value
  )

  if(!school) return

  if(compareList.value.length >= 3){
    compareError.value = 'Chỉ có thể so sánh tối đa 3 trường.'
    return
  }

  if(!compareList.value.some(item => item.id === school.id)){
    compareList.value = [...compareList.value, school]
    persistCompare()
    compareAddKey.value = ''
    await loadCompareDetails()
  }
}

async function removeCompareSchool(school){
  compareList.value = compareList.value.filter(
    item => item.id !== school.id
  )

  const nextDetails = { ...compareDetails.value }
  delete nextDetails[school.id]
  compareDetails.value = nextDetails

  persistCompare()
}

async function goToCompare(){
  activeTab.value = 'compare'
  await loadCompareDetails()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function compareYearScore(detail, program, year){
  const item = program?.history?.[String(year)]
  return item ? Number(item.cutoff_score).toFixed(2) : '—'
}
function normalizeConnectionUser(user){
  const roleLabel = user.role === 'mentor'
    ? (
        user.target_major
          ? `Mentor • ${user.target_major}`
          : 'Mentor UniConnect'
      )
    : (
        user.target_major
          ? `Quan tâm • ${user.target_major}`
          : 'Thành viên UniConnect'
      )

  return {
    id: user.id,
    name: user.name,
    avatar_url: user.avatar_url || '',
    initials: user.initials,
    role: roleLabel,
    city: user.city || '',
    followers: Number(user.followers_count || 0),
    following: Boolean(user.followed_by_me),
    isMentor: user.role === 'mentor' || Boolean(user.is_staff),
  }
}

async function loadMentorSuggestions(){
  mentorLoading.value = true
  mentorError.value = ''

  try{
    const users = await fetchConnectionSuggestions(6)
    mentorSuggestions.value = users.map(normalizeConnectionUser)
  }catch(error){
    mentorSuggestions.value = []
    mentorError.value = error.message || 'Không tải được gợi ý kết nối.'
  }finally{
    mentorLoading.value = false
  }
}

async function toggleMentorConnection(mentor){
  if(!currentUser.value){
    openAuth('login')
    return
  }

  connectionBusy.value = {
    ...connectionBusy.value,
    [mentor.id]: true,
  }

  try{
    const result = await toggleFollow(mentor.id)
    mentor.following = Boolean(result.following)
    mentor.followers = Number(result.target?.followers_count || mentor.followers)
  }catch(error){
    mentorError.value = error.message || 'Không thể cập nhật kết nối.'
  }finally{
    connectionBusy.value = {
      ...connectionBusy.value,
      [mentor.id]: false,
    }
  }
}

async function loadCareer(){
  careerLoading.value = true
  careerError.value = ''

  try{
    const payload = await fetchCareerQuestions()
    careerQuestions.value = payload.questions || []
    careerDimensions.value = payload.dimensions || {}
    careerScale.value = payload.scale || {}
    careerDisclaimer.value = payload.disclaimer || ''

    if(currentUser.value){
      try{
        const historyPayload = await fetchCareerHistory()
        careerHistory.value = historyPayload.assessments || []
      }catch{
        careerHistory.value = []
      }
    }else{
      careerHistory.value = []
    }
  }catch(error){
    careerError.value = error.message || 'Không tải được trắc nghiệm hướng nghiệp.'
  }finally{
    careerLoading.value = false
  }
}

function answerCareer(questionId, value){
  careerAnswers[questionId] = Number(value)
}

function nextCareerQuestion(){
  if(careerIndex.value < careerQuestions.value.length - 1){
    careerIndex.value += 1
  }
}

function previousCareerQuestion(){
  if(careerIndex.value > 0){
    careerIndex.value -= 1
  }
}

function resetCareerQuiz(){
  for(const key of Object.keys(careerAnswers)){
    delete careerAnswers[key]
  }
  careerIndex.value = 0
  careerResult.value = null
  careerError.value = ''
}

function openCareerHistory(item){
  const scores = item?.scores || {}

  const topDimensions = ['R','I','A','S','E','C']
    .map(code => ({
      code,
      ...(scores[code] || {}),
    }))
    .sort((a,b) => Number(b.percent || 0) - Number(a.percent || 0))
    .slice(0,3)

  careerResult.value = {
    ...item,
    top_dimensions: topDimensions,
    disclaimer: careerDisclaimer.value,
  }

  careerError.value = ''
  window.scrollTo({
    top: 0,
    behavior: 'smooth',
  })
}

async function submitCareerQuiz(){
  careerError.value = ''

  if(!currentUser.value){
    openAuth('login')
    careerError.value = 'Đăng nhập xong, quay lại và bấm “Xem kết quả” để lưu bài trắc nghiệm.'
    return
  }

  if(careerAnsweredCount.value !== careerQuestions.value.length){
    careerError.value = `Bạn còn ${careerQuestions.value.length - careerAnsweredCount.value} câu chưa trả lời.`
    return
  }

  careerSubmitting.value = true

  try{
    const payload = await submitCareerAssessment(
      { ...careerAnswers }
    )

    careerResult.value = {
      ...payload.assessment,
      top_dimensions: payload.top_dimensions || [],
      disclaimer: payload.disclaimer || careerDisclaimer.value,
    }

    const historyPayload = await fetchCareerHistory()
    careerHistory.value = historyPayload.assessments || []
  }catch(error){
    careerError.value = error.message || 'Không thể lưu kết quả hướng nghiệp.'
  }finally{
    careerSubmitting.value = false
  }
}

function useCareerMajor(major){
  form.major = major.major_name
  form.majorCode = major.major_code || ''
  activeTab.value = 'advisor'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function normalizeSocialPost(post){
  return {
    id: post.id,
    images: post.images || [],
    poll: post.poll || null,
    avatar: post.author?.avatar_url || '',
    canEdit: Boolean(post.can_edit),
    authorId: post.author?.id,
    author: post.author?.name || 'Thành viên',
    initials: post.author?.initials || 'U',
    verified: Boolean(post.author?.verified),
    role: post.author?.verified ? 'Thành viên xác minh' : 'Thành viên cộng đồng',
    time: post.time || '',
    content: post.content || '',
    tags: post.tag ? [post.tag] : [],
    likes: Number(post.likes_count || 0),
    liked: Boolean(post.liked_by_me),
    comments: Number(post.comments_count || 0),
    saves: Number(post.saves_count || 0),
    saved: Boolean(post.saved_by_me),
    topComments: (post.top_comments || []).map(comment => ({
      id: comment.id,
      author: comment.author?.name || 'Thành viên',
      initials: comment.author?.initials || 'U',
      avatar: comment.author?.avatar_url || '',
      content: comment.content || '',
      time: comment.time || '',
    })),
    category: post.category || 'general',
    categoryLabel: post.category_label || 'Dành cho bạn',
  }
}

async function loadSocialPosts(){
  socialLoading.value = true
  socialError.value = ''

  try{
    const category = feedCategoryMap[feedFilter.value] || ''
    const data = await fetchPosts(category, feedSearch.value)
    posts.value = data.map(normalizeSocialPost)
  }catch(error){
    posts.value = []
    socialError.value = error.message || 'Không tải được bảng tin.'
  }finally{
    socialLoading.value = false
  }
}

async function searchFeed(query='') {
  feedSearch.value=query; searchOpen.value=false
  activeTab.value='social'; await loadSocialPosts()
}

async function loadSavedPostList(){
  if(!currentUser.value){
    posts.value = []
    socialError.value = 'Bạn cần đăng nhập để xem bài đã lưu.'
    return
  }

  socialLoading.value = true
  socialError.value = ''

  try{
    const data = await fetchSavedPosts()
    posts.value = data.map(normalizeSocialPost)
  }catch(error){
    posts.value = []
    socialError.value = error.message || 'Không tải được bài đã lưu.'
  }finally{
    socialLoading.value = false
  }
}

async function likePost(post){
  if(!currentUser.value){
    openAuth('login')
    return
  }

  socialActionBusy.value = {
    ...socialActionBusy.value,
    [`like-${post.id}`]: true,
  }

  try{
    const result = await togglePostLike(post.id)
    post.liked = Boolean(result.liked)
    post.likes = Number(result.likes_count || 0)
  }catch(error){
    socialError.value = error.message || 'Không thể cập nhật lượt thích.'
  }finally{
    socialActionBusy.value = {
      ...socialActionBusy.value,
      [`like-${post.id}`]: false,
    }
  }
}

async function sharePost(post){
  const url = `${window.location.origin}${window.location.pathname}?post=${post.id}`

  try{
    if(navigator.share){
      await navigator.share({
        title: 'UniConnect AI',
        text: post.content.slice(0, 120),
        url,
      })
      return
    }

    await navigator.clipboard.writeText(url)
    notify('Đã sao chép liên kết bài viết.')
  }catch(error){
    if(error.name!=='AbortError') notify('Không thể sao chép tự động. Liên kết: '+url)
  }
}

async function savePost(post){
  if(!currentUser.value){
    openAuth('login')
    return
  }

  socialActionBusy.value = {
    ...socialActionBusy.value,
    [`save-${post.id}`]: true,
  }

  try{
    const result = await togglePostSave(post.id)
    post.saved = Boolean(result.saved)
    post.saves = Number(result.saves_count || 0)

    if(activeTab.value === 'saved' && !post.saved){
      posts.value = posts.value.filter(item => item.id !== post.id)
    }
  }catch(error){
    socialError.value = error.message || 'Không thể lưu bài viết.'
  }finally{
    socialActionBusy.value = {
      ...socialActionBusy.value,
      [`save-${post.id}`]: false,
    }
  }
}

function toggleCommentBox(postId){
  commentOpen[postId] = !commentOpen[postId]
}

async function submitComment(post){
  const content = String(commentDrafts[post.id] || '').trim()

  if(!content) return

  if(!currentUser.value){
    openAuth('login')
    return
  }

  socialActionBusy.value = {
    ...socialActionBusy.value,
    [`comment-${post.id}`]: true,
  }

  try{
    const comment = await createComment(post.id, content)

    post.comments += 1
    post.topComments = [
      {
        id: comment.id,
        author: comment.author?.name || profile.value.name,
        initials: comment.author?.initials || profile.value.initials,
        avatar: comment.author?.avatar_url || currentUser.value?.avatar_url || '',
        content: comment.content,
        time: comment.time || 'Vừa xong',
      },
      ...(post.topComments || []),
    ].slice(0, 2)

    commentDrafts[post.id] = ''
  }catch(error){
    socialError.value = error.message || 'Không thể gửi bình luận.'
  }finally{
    socialActionBusy.value = {
      ...socialActionBusy.value,
      [`comment-${post.id}`]: false,
    }
  }
}
function syncAdvisorFromProfile(user){
  const p = user?.profile
  if(!p) return

  if(p.expected_score !== null && p.expected_score !== undefined && p.expected_score !== ''){
    form.score = Number(p.expected_score)
  }
  if(p.target_combination && combinationOptions.includes(p.target_combination)){
    form.combination = p.target_combination
  }
  if(p.target_major){
    form.major = p.target_major
    form.majorCode = ''
  }
  if(p.city && cityOptions.includes(p.city)){
    form.city = p.city
  }
}

async function refreshAuth(){
  try{
    const user = await getMe()
    currentUser.value = user
    if(user) syncAdvisorFromProfile(user)
  }catch{
    currentUser.value = null
  }
}

function openAdmin() {
  profileOpen.value = false
  window.location.assign('/admin/')
}

function openAuth(mode='login'){
  authMode.value = mode
  authOpen.value = true
  profileOpen.value = false
}

async function onAuthenticated(user){
  currentUser.value = user
  if (user.is_staff) {
    openAdmin()
    return
  }
  syncAdvisorFromProfile(user)

  chatConversationId.value = ''
  sessionStorage.removeItem(
    'uniconnect-ai-chat-id'
  )

  await Promise.all([
    loadMentorSuggestions(),
    loadSavedUniversities(),
    loadAIChatHistory(),
  ])

  if(activeTab.value === 'quiz'){
    await loadCareer()
  }

  if(activeTab.value === 'saved'){
    await Promise.all([
      loadSavedPostList(),
      loadSavedUniversities(),
    ])
  }else if(activeTab.value === 'social'){
    await loadSocialPosts()
  }
}

function onProfileUpdated(user){
  currentUser.value = user
  syncAdvisorFromProfile(user)
  posts.value.forEach(post=>{ if(post.authorId===user.id) { post.avatar=user.avatar_url || ''; post.author=user.name } })
}

async function logoutCurrent(){
  try{
    await logoutAccount()
  }finally{
    currentUser.value = null
    profileOpen.value = false
    profileEditorOpen.value = false
    savedUniversities.value = []
    await startNewChat()

    catalogSchools.value.forEach(
      school => {
        school.saved = false
      }
    )

    if(activeTab.value === 'saved'){
      activeTab.value = 'social'
    }

    await Promise.all([loadSocialPosts(),loadMentorSuggestions()])
  }
}

function openCreatePost(){
  if(!currentUser.value){
    openAuth('login')
    return
  }
  creatingPost.value = true
}

async function publishPost(){
  const content = newPost.value.trim()

  if(!content) return

  if(!currentUser.value){
    creatingPost.value = false
    openAuth('login')
    return
  }

  socialActionBusy.value = {
    ...socialActionBusy.value,
    createPost: true,
  }

  try{
    const options = pollDraft.value.map(o=>o.trim()).filter(Boolean)
    if(pollEnabled.value && (options.length<2 || new Set(options.map(o=>o.toLowerCase())).size!==options.length)) throw new Error('Bình chọn cần ít nhất 2 lựa chọn khác nhau.')
    const body = new FormData()
    body.append('content',content)
    body.append('category',newPostCategory.value)
    body.append('tag',newPostTag.value)
    body.append('poll_options',JSON.stringify(pollEnabled.value?options:[]))
    postImages.value.forEach(i=>body.append('images',i.file))
    const created = await createPost(body)

    const mapped = normalizeSocialPost(created)

    if(activeTab.value !== 'social'){
      activeTab.value = 'social'
    }

    feedFilter.value = 'Dành cho bạn'
    posts.value = [mapped, ...posts.value.filter(post => post.id !== mapped.id)]
    newPost.value = ''
    clearImages(); pollEnabled.value=false; pollDraft.value=['','']; composerError.value=''
    creatingPost.value = false
    notify('Đã chia sẻ bài viết với cộng đồng.')
  }catch(error){
    composerError.value = error.message || 'Không thể đăng bài.'
  }finally{
    socialActionBusy.value = {
      ...socialActionBusy.value,
      createPost: false,
    }
  }
}

async function scrollChatToBottom(){ await nextTick(); if(chatBox.value) chatBox.value.scrollTop=chatBox.value.scrollHeight }
function chatUIContext(){
  return {
    score: Number(form.score),
    combination: form.combination,
    major: form.major.trim(),
    major_code: form.majorCode || '',
    city: form.city,
  }
}

function mapChatMessage(item){
  return {
    id: item.id || `chat-${Date.now()}-${Math.random()}`,
    role: item.role || 'assistant',
    text: item.text || '',
    intent: item.intent || '',
    cards: item.cards || [],
    suggestions: item.suggestions || [],
    diagnostics: item.diagnostics || {},
    created_at: item.created_at || '',
  }
}

async function loadAIChatHistory(){
  chatError.value = ''

  try{
    const payload = await fetchAIChatHistory(
      chatConversationId.value
    )

    if(payload.conversation_id){
      chatConversationId.value = String(
        payload.conversation_id
      )
      sessionStorage.setItem(
        'uniconnect-ai-chat-id',
        chatConversationId.value
      )
    }

    const history = (payload.messages || []).map(
      mapChatMessage
    )

    chatMessages.value = history.length
      ? history
      : [defaultChatGreeting]
  }catch(error){
    chatMessages.value = [defaultChatGreeting]
    chatError.value =
      error.message || 'Không tải được lịch sử AI Chat.'
  }

  await scrollChatToBottom()
}

async function startNewChat(){
  chatInput.value = ''
  chatError.value = ''
  chatMessages.value = [
    {
      ...defaultChatGreeting,
      id: `local-greeting-${Date.now()}`,
    }
  ]

  try{
    const payload = await createAIChatConversation()
    chatConversationId.value = String(
      payload.conversation_id || ''
    )

    if(chatConversationId.value){
      sessionStorage.setItem(
        'uniconnect-ai-chat-id',
        chatConversationId.value
      )
    }else{
      sessionStorage.removeItem(
        'uniconnect-ai-chat-id'
      )
    }
  }catch(error){
    chatConversationId.value = ''
    sessionStorage.removeItem(
      'uniconnect-ai-chat-id'
    )
    chatError.value =
      error.message || 'Không tạo được cuộc trò chuyện mới.'
  }
}

function resolveChatSchool(card){
  return resolveCatalogSchool({
    university_key: card.university_key || '',
    university_name: card.university_name || '',
    name: card.university_name || '',
  })
}

async function openChatSchool(card){
  const school = resolveChatSchool(card)

  if(!school){
    chatError.value =
      'Trường này chưa ánh xạ được với catalog sạch hiện tại.'
    return
  }

  await openUniversity(school)
}

async function useChatRecommendation(card){
  if(card.major_name){
    form.major = card.major_name
  }

  if(card.major_code){
    form.majorCode = card.major_code
  }

  activeTab.value = 'advisor'
  window.scrollTo({
    top: 0,
    behavior: 'smooth',
  })

  await runAdvisor(false)
}

function useHistoryMajor(card){
  form.major = card.major_name || form.major
  form.majorCode = card.major_code || ''
  activeTab.value = 'advisor'
  window.scrollTo({
    top: 0,
    behavior: 'smooth',
  })
}

async function sendChat(preset=''){
  const message = String(
    preset || chatInput.value
  ).trim()

  if(!message || chatLoading.value) return

  chatMessages.value.push({
    id: `user-${Date.now()}`,
    role: 'user',
    text: message,
    intent: 'user',
    cards: [],
    suggestions: [],
  })

  chatInput.value = ''
  chatLoading.value = true
  chatError.value = ''

  await scrollChatToBottom()

  try{
    const payload = await sendAIChatMessage({
      message,
      conversationId:
        chatConversationId.value,
      uiContext:
        chatUIContext(),
    })

    if(payload.conversation_id){
      chatConversationId.value = String(
        payload.conversation_id
      )
      sessionStorage.setItem(
        'uniconnect-ai-chat-id',
        chatConversationId.value
      )
    }

    if(payload.context){
      if(payload.context.score !== undefined && payload.context.score !== null){
        form.score = Number(
          payload.context.score
        )
      }

      if(payload.context.combination !== undefined){
        form.combination =
          payload.context.combination
      }

      if(payload.context.major !== undefined){
        form.major =
          payload.context.major
      }

      if(payload.context.major_code !== undefined){
        form.majorCode =
          payload.context.major_code || ''
      }

      if(payload.context.city !== undefined && payload.context.city !== null){
        form.city =
          payload.context.city
      }
    }

    chatMessages.value.push(
      mapChatMessage(
        payload.reply || {}
      )
    )
  }catch(error){
    chatError.value =
      error.message || 'AI Chat chưa phản hồi được.'

    chatMessages.value.push({
      id: `error-${Date.now()}`,
      role: 'assistant',
      text: `Mình chưa xử lý được yêu cầu này: ${chatError.value}`,
      intent: 'error',
      cards: [],
      suggestions: [],
    })
  }finally{
    chatLoading.value = false
    await scrollChatToBottom()
  }
}

function scheduleLiveAdvisor(){
  if(!hasSubmitted.value||activeTab.value!=='advisor') return
  clearTimeout(advisorDebounce); advisorDebounce=setTimeout(()=>runAdvisor(true),500)
}
function advisorReasonText(reason){
  return {
    NO_MAJOR_MATCH:
      'Không tìm thấy đúng chương trình/mã ngành này trong tập dự đoán 2027.',
    NO_COMBINATION_MATCH:
      `Có ngành phù hợp nhưng chưa có chương trình xác minh tổ hợp ${form.combination}.`,
    NO_LOCATION_MATCH:
      `Có ngành + tổ hợp phù hợp nhưng chưa có chương trình đủ dữ liệu tại ${strictCity.value || form.city}.`,
    NO_FRESH_2026_HISTORY:
      'Có chương trình phù hợp nhưng chưa có dữ liệu thực tế 2026 đủ điều kiện cho chương trình đủ dữ liệu.',
    OK:
      '',
  }[reason] || 'Không có chương trình đáp ứng đồng thời toàn bộ điều kiện strict.'
}

async function tryAdvisorCombination(code){
  form.combination = code
  await runAdvisor(false,{
    expandedNationwide:false,
  })
}

function showNationwideAlternatives(){
  const rows = advisorAlternatives.value.nationwide_verified || []

  if(!rows.length) return

  aiResults.value = rows
  advisorResultScope.value = 'NATIONWIDE_EXPANDED'

  window.scrollTo({
    top: document.querySelector('.results-section')?.offsetTop || 0,
    behavior:'smooth',
  })
}

async function runAdvisor(silent=false, options={}){
  const requestNumber = ++advisorRequest
  apiError.value = ''
  apiLoading.value = true

  if(!silent){
    hasSubmitted.value = true
  }

  const expandedNationwide = Boolean(options.expandedNationwide)
  const requestCity = expandedNationwide ? '' : form.city

  if(!expandedNationwide){
    strictCity.value = form.city
  }

  try{
    const response = await fetch('/api/ai/recommend/',{
      method:'POST',
      headers:{
        'Content-Type':'application/json; charset=utf-8'
      },
      body:JSON.stringify({
        score:Number(form.score),
        combination:form.combination,
        major:form.major.trim(),
        major_code:form.majorCode || '',
        city:requestCity,
        top:Number(form.top)
      })
    })

    const payload = await response.json()
    if(requestNumber!==advisorRequest) return

    if(!response.ok || !payload.success){
      throw new Error(
        payload.error || 'Không thể lấy kết quả tư vấn.'
      )
    }

    aiResults.value = payload.results || []
    advisorDiagnostics.value = payload.diagnostics || null
    otherAdmissionMethods.value = payload.other_admission_methods || []
    advisorAlternatives.value = payload.alternatives || {
      same_city_unverified_combination: [],
      nationwide_verified: [],
      same_city_historical: [],
      related_major_name: [],
    }
    lastModelInfo.value = payload.model_info || null
    lastAdvisorReason.value = payload.reason || (
      aiResults.value.length ? 'OK' : 'NO_RESULTS'
    )
    advisorResultScope.value = expandedNationwide
      ? 'NATIONWIDE_EXPANDED'
      : 'STRICT'
  }catch(error){
    if(requestNumber!==advisorRequest) return
    aiResults.value = []
    advisorDiagnostics.value = null
    otherAdmissionMethods.value = []
    advisorAlternatives.value = {
      same_city_unverified_combination: [],
      nationwide_verified: [],
      same_city_historical: [],
      related_major_name: [],
    }
    lastAdvisorReason.value = 'ERROR'
    advisorResultScope.value = 'STRICT'
    apiError.value =
      `${error.message} Hãy kiểm tra Django đang chạy tại http://127.0.0.1:8000.`
  }finally{
    if(requestNumber===advisorRequest) apiLoading.value = false
  }
}

async function expandAdvisorNationwide(){
  await runAdvisor(false,{
    expandedNationwide:true,
  })
}

async function restoreStrictAdvisor(){
  await runAdvisor(false,{
    expandedNationwide:false,
  })
}

function recommendationClass(level){ return {'AN TOÀN':'safe','PHÙ HỢP':'fit','THỬ SỨC':'reach','RỦI RO CAO':'risk'}[level]||'neutral' }
function profileFit(result){
  const gap=Number(result.score_gap||0)
  const base=result.recommendation_level==='AN TOÀN'?92:result.recommendation_level==='PHÙ HỢP'?82:result.recommendation_level==='THỬ SỨC'?68:48
  const historyBonus=Math.min(4,Math.max(0,Number(result.history_count||1)-1))
  return Math.max(35,Math.min(98,Math.round(base+Math.min(4,Math.max(-4,gap/3))+historyBonus)))
}
function displayUniversityName(name){ return String(name||'').replace(/Kiếntrúc/gi,'Kiến trúc').replace(/\s+/g,' ').trim() }

watch(feedFilter, async()=>{
  if(activeTab.value === 'social'){
    await loadSocialPosts()
  }
})

watch(activeTab, async(tab)=>{
  if(tab === 'social'){
    await loadSocialPosts()
  }else if(tab === 'saved'){
    await Promise.all([
      loadSavedPostList(),
      loadSavedUniversities(),
    ])
  }else if(tab === 'compare'){
    await loadCompareDetails()
  }else if(tab === 'quiz'){
    if(careerQuestions.value.length === 0){
      await loadCareer()
    }else if(currentUser.value){
      try{
        const historyPayload = await fetchCareerHistory()
        careerHistory.value = historyPayload.assessments || []
      }catch{
        careerHistory.value = []
      }
    }
  }
})

watch(darkMode,setTheme)
watch(()=>[form.score,form.combination,form.major,form.city],scheduleLiveAdvisor)
onMounted(async()=>{ setTheme(); updateCountdown(); countdownTimer=setInterval(updateCountdown,1000); await Promise.all([refreshAuth(),loadCatalogSchools(),loadSocialPosts(),loadMentorSuggestions(),loadAIChatHistory()]); if(pendingPost) await openSharedPost(pendingPost) })
onBeforeUnmount(()=>{ clearInterval(countdownTimer); clearTimeout(advisorDebounce) })
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-inner">
        <button class="mobile-menu-btn icon-btn" @click="mobileMenu=!mobileMenu"><Menu :size="20"/></button>

        <button class="brand" @click="setTab('advisor')">
          <span class="brand-mark"><BookOpen :size="31" stroke-width="1.8"/><i></i></span>
          <span class="brand-copy"><strong>UniConnect<span>AI</span></strong><small>Cùng bạn chọn hướng tương lai</small></span>
        </button>

        <button class="global-search" @click="searchOpen=true">
          <Search :size="18"/><span>Tìm trường, ngành học, bài viết…</span><kbd>Ctrl K</kbd>
        </button>

        <label class="header-location"><MapPin :size="14"/><select v-model="form.city" aria-label="Khu vực quan tâm"><option v-for="city in cityOptions" :key="city">{{ city }}</option></select></label>

        <div class="top-actions">
          <button class="icon-btn" @click="toggleDark" :aria-label="darkMode ? 'Dùng giao diện sáng' : 'Dùng giao diện tối'"><Sun v-if="darkMode" :size="19"/><Moon v-else :size="19"/></button>

          <CommunityInbox ref="communityInbox" :user="currentUser" :contacts="mentorSuggestions" @login="openAuth('login')" @open-post="openSharedPost"/>
          <div class="action-popover">
            <template v-if="currentUser">
              <button class="profile-button" @click="profileOpen=!profileOpen;notificationOpen=false;messageOpen=false">
                <span class="avatar"><img v-if="currentUser?.avatar_url" :src="currentUser.avatar_url" alt="Ảnh đại diện của bạn"/><template v-else>{{ profile.initials }}</template></span>
                <span class="profile-meta">
                  <strong>{{ profile.name }}</strong>
                  <small>{{ currentUser.profile?.role === 'mentor' ? 'Mentor' : 'Thành viên' }}</small>
                </span>
                <ChevronDown :size="15"/>
              </button>

              <div v-if="profileOpen" class="popover-panel profile-panel">
                <div class="popover-account">
                  <span class="avatar mini"><img v-if="currentUser?.avatar_url" :src="currentUser.avatar_url" alt=""/><template v-else>{{ profile.initials }}</template></span>
                  <div>
                    <strong>{{ profile.name }}</strong>
                    <small>{{ currentUser.email }}</small>
                  </div>
                </div>
                <button @click="profileEditorOpen=true;profileOpen=false"><CircleUserRound :size="16"/> Hồ sơ cá nhân</button>
                <button @click="profileEditorOpen=true;profileOpen=false"><Settings2 :size="16"/> Cài đặt hồ sơ AI</button>
                <button v-if="currentUser.is_staff" @click="openAdmin"><ShieldCheck :size="16"/> Trang quản trị</button>
                <button class="logout-menu-item" @click="logoutCurrent"><X :size="16"/> Đăng xuất</button>
              </div>
            </template>

            <button v-else class="login-header-btn" @click="openAuth('login')">
              <CircleUserRound :size="17"/>
              <span>Đăng nhập</span>
            </button>
          </div>
        </div>
      </div>
    </header>

    <div class="dashboard-grid">
      <aside class="left-sidebar" :class="{open:mobileMenu}">
        <div class="sidebar-scroll">
          <div class="sidebar-caption">KHÔNG GIAN CỦA BẠN</div>
          <nav class="nav-stack">
            <button v-for="item in navItems" :key="item.id" class="nav-item" :class="{active:activeTab===item.id}" @click="setTab(item.id)">
              <span class="nav-icon"><component :is="item.icon" :size="19"/></span>
              <span><strong>{{ item.label }}</strong><small>{{ item.note }}</small></span>
            </button>
          </nav>

          <div class="sidebar-divider"></div>

          <section v-if="activeTab==='advisor'" class="filter-card">
            <div class="filter-head"><div><Sparkles :size="17"/><strong>Lọc nhanh AI</strong></div><span class="live-dot">LIVE</span></div>
            <label class="field-label">Điểm dự kiến <strong>{{ Number(form.score).toFixed(1) }}</strong></label>
            <input v-model.number="form.score" type="range" min="10" max="30" step="0.25" class="score-range"/>
            <div class="range-labels"><span>10</span><span>20</span><span>30</span></div>

            <label class="field-label top-gap">Khối thi</label>
            <div class="combo-grid">
              <button v-for="combo in combinationOptions" :key="combo" class="combo-chip" :class="{selected:form.combination===combo}" @click="form.combination=combo">{{ combo }}</button>
            </div>

            <label class="field-label top-gap">Ngành mong muốn</label>
            <input v-model="form.major" class="side-input" placeholder="VD: Công nghệ thông tin"/>

            <div class="filter-data-note">Bạn có thể kiểm tra học phí ở thông báo chính thức của từng trường.</div>

            <button class="primary-btn full" @click="setTab('advisor');runAdvisor()"><Zap :size="17"/> Phân tích bằng AI</button>
          </section>

          <div class="privacy-note"><ShieldCheck :size="17"/><span><strong>Dữ liệu minh bạch</strong><small>Kết quả AI hiển thị năm dữ liệu gần nhất và sai số hiệu chỉnh.</small></span></div>
        </div>
      </aside>

      <main class="content-area">
        <div class="mobile-page-title"><span>UniConnect AI</span><button class="icon-btn" @click="searchOpen=true"><Search :size="18"/></button></div>

        <template v-if="activeTab==='advisor' || activeTab==='social'">
          <CampusHero @search="searchFromCampus"/>
          <nav class="campus-shortcuts" aria-label="Khám phá nhanh">
            <button v-for="item in campusShortcuts" :key="item.id" :class="{active:activeTab===item.id}" @click="setTab(item.id)"><component :is="item.icon" :size="22" stroke-width="1.6"/><span>{{ item.label }}</span></button>
          </nav>
        </template>

        <template v-if="activeTab==='advisor'">
          <section class="advisor-panel card">
            <div class="section-heading">
              <div><span class="section-kicker">BẮT ĐẦU TỪ ĐIỀU BẠN MONG MUỐN</span><h2>Cùng tìm trường phù hợp với bạn</h2><p>Điền một chút thông tin. Mình sẽ giúp bạn đối chiếu các lựa chọn.</p></div>
              <div class="model-pill"><span></span> {{ lastModelInfo ? 'Đã đối chiếu dữ liệu' : 'Dữ liệu tuyển sinh 2023–2026' }}</div>
            </div>

            <div class="advisor-form">
              <label><span>Điểm THPT</span><div class="input-with-icon"><Target :size="17"/><input v-model.number="form.score" type="number" min="0" max="30" step="0.25"/></div></label>
              <label><span>Tổ hợp</span><div class="input-with-icon"><FileText :size="17"/><select v-model="form.combination"><option v-for="c in combinationOptions" :key="c">{{ c }}</option></select></div></label>
              <label class="wide">
                <span>
                  Ngành quan tâm
                  <small v-if="form.majorCode" class="exact-major-code">Mã {{ form.majorCode }}</small>
                </span>
                <div class="input-with-icon">
                  <GraduationCap :size="17"/>
                  <input
                    v-model="form.major"
                    placeholder="Công nghệ thông tin"
                    @input="form.majorCode=''"
                  />
                </div>
              </label>
              <label><span>Tỉnh / Thành</span><div class="input-with-icon"><MapPin :size="17"/><select v-model="form.city"><option v-for="city in cityOptions" :key="city">{{ city }}</option></select></div></label>
              <button class="analyze-btn" :disabled="apiLoading" @click="runAdvisor()"><span v-if="apiLoading" class="spinner"></span><Sparkles v-else :size="18"/>{{ apiLoading?'AI đang phân tích...':'Phân tích hồ sơ' }}</button>
            </div>
            <div v-if="apiError" class="error-banner"><X :size="17"/><span>{{ apiError }}</span></div>
          </section>

          <section class="results-section">
            <div class="section-heading compact">
              <div><span class="section-kicker">LỰA CHỌN DÀNH CHO BẠN</span><h2>Những ngôi trường để bạn cân nhắc</h2></div>
              <div v-if="hasSubmitted&&!apiLoading" class="result-count">
                {{ aiResults.length }}
                {{ advisorResultScope==='STRICT' ? 'chương trình đủ dữ liệu' : 'kết quả mở rộng toàn quốc' }}
              </div>
            </div>

            <div v-if="apiLoading" class="results-skeleton">
              <div v-for="n in 3" :key="n" class="skeleton-card"><span></span><div><i></i><i></i><i></i></div></div>
            </div>

            <div v-else-if="!hasSubmitted" class="empty-state premium">
              <div class="empty-orb"><Bot :size="28"/></div><h3>Sẵn sàng phân tích hồ sơ</h3>
              <p>Nhập điểm, tổ hợp, ngành và khu vực. UniConnect AI chỉ dùng chương trình có dữ liệu thực tế đến 2026 và tổ hợp được xác minh.</p>
              <button class="primary-btn" @click="runAdvisor()"><Sparkles :size="17"/> Chạy phân tích đầu tiên</button>
            </div>

            <div v-else-if="aiResults.length===0" class="advisor-zero-wrap">
              <div class="empty-state advisor-empty-state">
                <div class="empty-orb neutral"><Search :size="27"/></div>
                <h3>Chưa có chương trình đủ dữ liệu</h3>
                <p>{{ advisorReasonText(lastAdvisorReason) }}</p>

                <div
                  v-if="advisorDiagnostics"
                  class="advisor-diagnostic-strip"
                >
                  <span>
                    <small>Khớp ngành</small>
                    <strong>{{ advisorDiagnostics.major_match_count || 0 }}</strong>
                  </span>
                  <span>
                    <small>Có dữ liệu 2026</small>
                    <strong>{{ advisorDiagnostics.fresh_2026_count || 0 }}</strong>
                  </span>
                  <span>
                    <small>Xác minh {{ form.combination }}</small>
                    <strong>{{ advisorDiagnostics.verified_combination_fresh_count || 0 }}</strong>
                  </span>
                </div>

                <div
                  v-if="advisorCombinationSuggestions.length"
                  class="advisor-combo-suggestions"
                >
                  <span>Tổ hợp có dữ liệu cho ngành này:</span>

                  <button
                    v-for="item in advisorCombinationSuggestions.slice(0,8)"
                    :key="item.combination"
                    :class="{active:item.combination===form.combination}"
                    @click="tryAdvisorCombination(item.combination)"
                  >
                    {{ item.combination }}
                    <small>{{ item.program_count }}</small>
                  </button>
                </div>

                <div class="advisor-empty-actions">
                  <button
                    v-if="advisorAlternatives.nationwide_verified?.length"
                    class="primary-btn"
                    @click="showNationwideAlternatives"
                  >
                    <MapPin :size="16"/>
                    Xem {{ advisorAlternatives.nationwide_verified.length }} kết quả đúng tổ hợp ngoài khu vực
                  </button>

                  <button
                    class="ghost-btn"
                    @click="setTab('universities')"
                  >
                    <Building2 :size="16"/>
                    Khám phá dữ liệu trường
                  </button>
                </div>

                <small>
                  Hệ thống không tự đổi tổ hợp, không giả dữ liệu 2026 và không trộn kết quả mở rộng vào nhóm strict.
                </small>
              </div>


            </div>

            <div v-else class="match-list">
              <div
                v-if="advisorResultScope==='NATIONWIDE_EXPANDED'"
                class="advisor-scope-banner"
              >
                <div>
                  <MapPin :size="17"/>
                  <span>
                    <strong>Kết quả mở rộng toàn quốc</strong>
                    <small>Giữ nguyên điểm, ngành và tổ hợp; chỉ bỏ điều kiện tỉnh/thành {{ strictCity }}.</small>
                  </span>
                </div>

                <button class="ghost-btn" @click="restoreStrictAdvisor">
                  Quay lại strict
                </button>
              </div>

              <article v-for="(result,index) in aiResults" :key="`${result.major_code}-${index}`" class="match-card">
                <div class="school-avatar ai"><GraduationCap :size="23"/></div>
                <div class="match-main">
                  <div class="match-topline">
                    <div><div class="verified-line"><ShieldCheck :size="14"/> Dữ liệu {{ result.last_actual_year }} • {{ result.combination_status }}</div><h3>{{ displayUniversityName(result.university_name) }}</h3></div>
                    <span class="level-badge" :class="recommendationClass(result.recommendation_level)">{{ result.recommendation_level }}</span>
                  </div>
                  <div class="program-line"><strong>{{ result.major_name }}</strong><span>{{ result.major_code }}</span></div>
                  <div class="match-metrics">
                    <div><small>Điểm dự đoán 2027</small><strong>{{ Number(result.predicted_cutoff_2027).toFixed(2) }}</strong></div>
                    <div><small>Điểm của bạn</small><strong>{{ Number(result.student_score).toFixed(2) }}</strong></div>
                    <div><small>Chênh lệch</small><strong :class="{positive:result.score_gap>=0}">{{ result.score_gap>0?'+':'' }}{{ Number(result.score_gap).toFixed(2) }}</strong></div>
                    <div><small>Lịch sử</small><strong>{{ result.history_count }} năm • {{ result.history_reliability }}</strong></div>
                  </div>
                  <div class="combination-line"><span>Tổ hợp xác minh</span><code>{{ result.eligible_combinations }}</code></div>
                  <div class="match-footer">
                    <span class="level-badge" :class="recommendationClass(result.recommendation_level)">{{ result.recommendation_level }}</span>
                    <span class="calibration-note">Hiệu chỉnh {{ result.calibration_scope }} • q80 ±{{ result.calibrated_error_q80 }} điểm</span>
                    <div class="match-actions">
                      <button class="ghost-btn" @click="openUniversity({name:displayUniversityName(result.university_name),short:result.major_code,city:form.city,field:result.major_name,fee:'Đang cập nhật',verified:true,accent:'linear-gradient(135deg,#4F46E5,#8B5CF6)'})">Xem chi tiết</button>
                      <button
                        class="soft-btn"
                        :class="{selected:isUniversitySaved({university_name:displayUniversityName(result.university_name)})}"
                        @click="saveAdvisorUniversity(result)"
                      >
                        <Bookmark
                          :size="15"
                          :fill="isUniversitySaved({university_name:displayUniversityName(result.university_name)}) ? 'currentColor' : 'none'"
                        />
                        {{ isUniversitySaved({university_name:displayUniversityName(result.university_name)}) ? 'Đã lưu trường' : 'Lưu trường' }}
                      </button>
                    </div>
                  </div>
                </div>
              </article>

              <div
                v-if="advisorResultScope==='STRICT' && aiResults.length<5 && advisorAlternativeCount"
                class="few-results-note card"
              >
                <Sparkles :size="18"/>
                <span>
                  <strong>Strict chỉ có {{ aiResults.length }} kết quả.</strong>
                  <small>
                    Backend còn tìm thấy {{ advisorAlternativeCount }} lựa chọn mở rộng có gắn nhãn.
                    Kết quả strict vẫn được giữ riêng để không làm sai logic tư vấn.
                  </small>
                </span>
              </div>
            </div>

              <section
                v-if="hasSubmitted && !apiLoading && advisorAlternativeCount && advisorResultScope==='STRICT'"
                class="advisor-alternatives"
              >
                <div class="section-heading compact">
                  <div>
                    <span class="section-kicker">GỢI Ý MỞ RỘNG CÓ GẮN NHÃN</span>
                    <h2>Thêm lựa chọn để bạn cân nhắc</h2>
                    <p>Các lựa chọn dưới đây có ghi rõ năm dữ liệu và thông tin còn cần kiểm tra. Điểm dự đoán không phải điểm chuẩn chính thức.</p>
                  </div>
                </div>

                <div
                  v-if="advisorAlternatives.same_city_unverified_combination?.length"
                  class="alternative-group card"
                >
                  <div class="alternative-group-head">
                    <span class="alternative-label warning">CẦN XÁC MINH TỔ HỢP</span>
                    <strong>Cùng khu vực • dữ liệu 2026 • nguồn chưa ghi rõ tổ hợp</strong>
                  </div>

                  <div class="alternative-row-list">
                    <div
                      v-for="item in advisorAlternatives.same_city_unverified_combination"
                      :key="`u-${item.university_name}-${item.major_code}`"
                      class="alternative-row"
                    >
                      <span>
                        <strong>{{ displayUniversityName(item.university_name) }}</strong>
                        <small>{{ item.major_name }} • {{ item.major_code }}</small>
                      </span>
                      <b>{{ Number(item.predicted_cutoff_2027).toFixed(2) }}</b>
                    </div>
                  </div>
                </div>

                <div
                  v-if="advisorAlternatives.nationwide_verified?.length"
                  class="alternative-group card"
                >
                  <div class="alternative-group-head">
                    <span class="alternative-label verified">ĐÚNG TỔ HỢP • NGOÀI KHU VỰC</span>
                    <strong>Dữ liệu 2026 và tổ hợp {{ form.combination }} đã xác minh</strong>
                  </div>

                  <div class="alternative-row-list">
                    <div
                      v-for="item in advisorAlternatives.nationwide_verified"
                      :key="`n-${item.university_name}-${item.major_code}`"
                      class="alternative-row"
                    >
                      <span>
                        <strong>{{ displayUniversityName(item.university_name) }}</strong>
                        <small>{{ item.major_name }} • {{ item.major_code }}</small>
                      </span>

                      <div>
                        <b>{{ Number(item.predicted_cutoff_2027).toFixed(2) }}</b>
                        <small>{{ item.recommendation_level }}</small>
                      </div>
                    </div>
                  </div>
                </div>

                <div
                  v-if="advisorAlternatives.same_city_historical?.length"
                  class="alternative-group card"
                >
                  <div class="alternative-group-head">
                    <span class="alternative-label stale">DỮ LIỆU CŨ HƠN</span>
                    <strong>Cùng khu vực + đúng tổ hợp nhưng actual gần nhất trước 2026</strong>
                  </div>

                  <div class="alternative-row-list">
                    <div
                      v-for="item in advisorAlternatives.same_city_historical"
                      :key="`h-${item.university_name}-${item.major_code}`"
                      class="alternative-row"
                    >
                      <span>
                        <strong>{{ displayUniversityName(item.university_name) }}</strong>
                        <small>{{ item.major_name }} • actual {{ item.last_actual_year }}</small>
                      </span>
                      <b>{{ Number(item.predicted_cutoff_2027).toFixed(2) }}</b>
                    </div>
                  </div>
                </div>

                <div
                  v-if="advisorAlternatives.related_major_name?.length"
                  class="alternative-group card"
                >
                  <div class="alternative-group-head">
                    <span class="alternative-label related">CÙNG NHÓM TÊN NGÀNH</span>
                    <strong>Mã ngành đang chọn quá cụ thể; đây là chương trình tên gần và đúng tổ hợp</strong>
                  </div>

                  <div class="alternative-row-list">
                    <div
                      v-for="item in advisorAlternatives.related_major_name.slice(0,5)"
                      :key="`r-${item.university_name}-${item.major_code}`"
                      class="alternative-row"
                    >
                      <span>
                        <strong>{{ displayUniversityName(item.university_name) }}</strong>
                        <small>{{ item.major_name }} • {{ item.major_code }}</small>
                      </span>
                      <b>{{ Number(item.predicted_cutoff_2027).toFixed(2) }}</b>
                    </div>
                  </div>
                </div>
              </section>
            <section v-if="hasSubmitted && !apiLoading && otherAdmissionMethods.length" class="official-methods card">
              <span class="section-kicker">ĐIỂM CÔNG BỐ CHÍNH THỨC · PHƯƠNG THỨC KHÁC</span>
              <h3>Trường còn xét bằng phương thức kết hợp</h3>
              <p>Các điểm dưới đây dùng học bạ hoặc chứng chỉ cùng điều kiện riêng. Chưa thể so trực tiếp với tổng {{ form.score }} điểm THPT hoặc kết luận khả năng trúng tuyển.</p>
              <div v-for="row in otherAdmissionMethods" :key="`${row.university_key}-${row.major_code}`" class="official-method-row">
                <div><strong>{{ row.university_name }}</strong><span>{{ row.major_name }} · {{ row.major_code }}</span><small>{{ row.admission_method }} · {{ row.year }}</small></div>
                <div><b>{{ Number(row.cutoff_score).toFixed(2) }}</b><a :href="row.source_url" target="_blank" rel="noopener noreferrer">Xem nguồn ↗</a></div>
              </div>
            </section>
            <div v-if="hasSubmitted&&aiResults.length" class="results-insight card">
              <div><Sparkles :size="20"/><span><strong>Tóm tắt AI</strong><small>{{ recommendationSummary['AN TOÀN'] }} An toàn • {{ recommendationSummary['PHÙ HỢP'] }} Phù hợp • {{ recommendationSummary['THỬ SỨC'] }} Thử sức</small></span></div>
              <div v-if="lastModelInfo" class="metric-inline"><span>Model</span><b>{{ lastModelInfo.method }}</b><span>Holdout</span><b>{{ lastModelInfo.holdout_samples }}</b><span>q80</span><b>{{ Number(lastModelInfo.error_q80).toFixed(2) }}</b></div>
            </div>
          </section>

          <section class="chat-card card">
            <div class="chat-head">
              <div class="chat-ai-icon"><Bot :size="22"/></div>
              <div>
                <strong>UniConnect AI Assistant</strong>
                <small><span class="online-dot"></span> Grounded vào model + dataset 2023–2026</small>
              </div>
              <button class="icon-btn" title="Cuộc trò chuyện mới" @click="startNewChat"><Plus :size="18"/></button>
            </div>

            <div v-if="chatError" class="chat-error-banner">{{ chatError }}</div>

            <div ref="chatBox" class="chat-messages">
              <div v-for="message in chatMessages" :key="message.id" class="message-row" :class="message.role">
                <div v-if="message.role==='assistant'" class="message-avatar"><Sparkles :size="15"/></div>

                <div class="chat-message-stack">
                  <div class="message-bubble chat-text">{{ message.text }}</div>
                  <small v-if="message.role==='assistant' && message.diagnostics?.answer_mode==='evidence_fallback'" class="chat-service-note">{{ ['rate_limit','daily_quota','quota_unavailable'].includes(message.diagnostics?.provider_reason) ? 'Gemini đang giới hạn lượt gọi' : 'Chưa kết nối được AI hội thoại' }} · Đang dùng kết quả tra cứu</small>

                  <div v-if="message.cards?.length" class="chat-rich-list">
                    <article v-for="(card,index) in message.cards" :key="`${message.id}-${index}`" class="chat-rich-card">
                      <template v-if="card.kind==='official_method'">
                        <span class="alternative-label warning">ĐIỂM CÔNG BỐ THEO PHƯƠNG THỨC · {{ card.year }}</span>
                        <h4>{{ card.university_name }}</h4>
                        <span class="chat-major-name">{{ card.major_name }} · {{ card.major_code }}</span>
                        <p>{{ card.admission_method }}: {{ Number(card.cutoff_score).toFixed(2) }} điểm. Cần kiểm tra đủ điều kiện và cách tính riêng; chưa so trực tiếp với tổng điểm THPT.</p>
                        <a :href="card.source_url" target="_blank" rel="noopener noreferrer">Xem thông báo chính thức ↗</a>
                      </template>
                      <template v-else-if="card.kind==='recommendation'">
                        <div class="chat-rich-head">
                          <span class="chat-scope-badge" :class="{strict:card.scope==='STRICT',expanded:card.scope!=='STRICT'}">{{ card.scope }}</span>
                          <span class="chat-cutoff">{{ Number(card.predicted_cutoff_2027).toFixed(2) }}</span>
                        </div>
                        <strong class="chat-school-name">{{ displayUniversityName(card.university_name) }}</strong>
                        <span class="chat-major-name">{{ card.major_name }} • {{ card.major_code }}</span>

                        <div class="chat-mini-metrics">
                          <span><small>Chênh lệch</small><b>{{ Number(card.score_gap) >= 0 ? '+' : '' }}{{ Number(card.score_gap).toFixed(2) }}</b></span>
                          <span><small>Mức tư vấn</small><b>{{ card.recommendation_level }}</b></span>
                          <span><small>Lịch sử</small><b>{{ card.history_reliability || '—' }}</b></span>
                        </div>

                        <div class="chat-rich-actions">
                          <button class="soft-btn" @click="useChatRecommendation(card)"><Bot :size="14"/> Dùng trong Advisor</button>
                          <button v-if="resolveChatSchool(card)" class="ghost-btn" @click="openChatSchool(card)"><Building2 :size="14"/> Xem trường</button>
                        </div>
                      </template>

                      <template v-else-if="card.kind==='history'">
                        <strong class="chat-school-name">{{ card.university_name }}</strong>
                        <span class="chat-major-name">{{ card.major_name }} • {{ card.major_code }}</span>

                        <div class="chat-history-grid">
                          <div v-for="year in (card.requested_years || [2023,2024,2025,2026])" :key="year">
                            <small>{{ year }}</small>
                            <strong>{{ card.history?.[String(year)] ? Number(card.history[String(year)].cutoff_score).toFixed(2) : '—' }}</strong>
                            <a v-for="url in (card.history?.[String(year)]?.source_urls || '').split('|').filter(Boolean)" :key="url" :href="url" target="_blank" rel="noopener noreferrer">Nguồn ↗</a>
                          </div>
                        </div>

                        <div class="chat-rich-actions">
                          <button class="soft-btn" @click="useHistoryMajor(card)"><Bot :size="14"/> Dùng ngành này</button>
                          <button v-if="resolveChatSchool(card)" class="ghost-btn" @click="openChatSchool(card)"><Building2 :size="14"/> Xem chi tiết</button>
                        </div>
                      </template>

                      <template v-else-if="card.kind==='compare'">
                        <strong class="chat-school-name">{{ card.university_name }}</strong>
                        <div class="chat-mini-metrics">
                          <span><small>Số ngành</small><b>{{ card.program_count }}</b></span>
                          <span><small>Độ phủ</small><b>{{ card.available_years?.length || 0 }}/4</b></span>
                          <span><small>Khoảng điểm</small><b>{{ card.score_min ?? '—' }}–{{ card.score_max ?? '—' }}</b></span>
                        </div>

                        <template v-if="card.major">
                          <span class="chat-major-name">{{ card.major.major_name }} • {{ card.major.major_code }}</span>
                          <div class="chat-history-grid">
                            <div v-for="year in [2023,2024,2025,2026]" :key="year">
                              <small>{{ year }}</small>
                              <strong>{{ card.major.history?.[String(year)] ? Number(card.major.history[String(year)].cutoff_score).toFixed(2) : '—' }}</strong>
                            </div>
                          </div>
                        </template>
                      </template>

                      <template v-else-if="card.kind==='aspirations'">
                        <div class="chat-rich-head">
                          <span class="chat-scope-badge" :class="{
                            'nv1': card.slot==='AN TOÀN',
                            'nv2': card.slot==='PHÙ HỢP',
                            'nv3': card.slot==='THỬ SỨC',
                          }">{{ card.advisory_level }}</span>
                          <span class="chat-cutoff" v-if="card.predicted_cutoff_2027">{{ Number(card.predicted_cutoff_2027).toFixed(2) }}</span>
                        </div>
                        <small class="chat-slot-desc">{{ card.slot_description }}</small>
                        <strong class="chat-school-name">{{ displayUniversityName(card.university_name) }}</strong>
                        <span class="chat-major-name">{{ card.major_name }} • {{ card.major_code }}</span>

                        <div class="chat-mini-metrics">
                          <span><small>Chênh lệch</small><b>{{ Number(card.score_gap) >= 0 ? '+' : '' }}{{ Number(card.score_gap).toFixed(2) }}</b></span>
                          <span><small>Mức tư vấn</small><b>{{ card.recommendation_level || card.advisory_level }}</b></span>
                          <span><small>Độ tin cậy</small><b>{{ card.history_reliability || '—' }}</b></span>
                        </div>

                        <div class="chat-rich-actions">
                          <button class="soft-btn" @click="useChatRecommendation(card)"><Bot :size="14"/> Dùng trong Advisor</button>
                          <button v-if="resolveChatSchool(card)" class="ghost-btn" @click="openChatSchool(card)"><Building2 :size="14"/> Xem trường</button>
                        </div>
                      </template>

                    </article>
                  </div>

                  <div v-if="message.role==='assistant' && message.suggestions?.length" class="chat-suggestion-row">
                    <button v-for="suggestion in message.suggestions" :key="suggestion" @click="sendChat(suggestion)">{{ suggestion }}</button>
                  </div>
                </div>
              </div>


              <div v-if="chatLoading" class="message-row assistant">
                <div class="message-avatar"><Sparkles :size="15"/></div>
                <div class="message-bubble thinking"><span></span><span></span><span></span><small>UniConnect AI đang soạn câu trả lời...</small></div>
              </div>
            </div>

            <div class="prompt-row"><button v-for="prompt in quickPrompts" :key="prompt" @click="sendChat(prompt)">{{ prompt }}</button></div>
            <div class="chat-input-row">
              <button class="icon-btn" disabled title="Chat hiện dùng dữ liệu text của project"><Paperclip :size="18"/></button>
              <input v-model="chatInput" @keyup.enter="sendChat()" placeholder="Hỏi: 24 điểm A01 CNTT ở Đà Nẵng nên chọn trường nào?"/>
              <button class="send-btn" :disabled="!chatInput.trim() || chatLoading" @click="sendChat()"><Send :size="17"/></button>
            </div>
          </section>
        </template>

        <template v-else-if="activeTab==='social'">
          <section class="page-intro">
            <div>
              <span class="section-kicker">GÓC CHIA SẺ</span>
              <h1>Chuyện chọn trường, cùng nhau chia sẻ</h1>
              <p>Một câu hỏi nhỏ hôm nay, một lựa chọn rõ ràng hơn ngày mai.</p>
            </div>
            <button class="primary-btn" @click="openCreatePost">
              <Plus :size="17"/> Tạo bài viết
            </button>
          </section>

          <section class="create-post card" @click="openCreatePost">
            <span class="avatar"><img v-if="currentUser?.avatar_url" :src="currentUser.avatar_url" alt="Ảnh đại diện của bạn"/><template v-else>{{ profile.initials }}</template></span>
            <div class="post-placeholder">
              {{ currentUser ? 'Bạn đang băn khoăn điều gì về chọn ngành, chọn trường?' : 'Đăng nhập để chia sẻ cùng cộng đồng UniConnect AI' }}
            </div>
            <button><ImageIcon :size="18"/> Ảnh</button>
            <button @click="pollEnabled=true"><Activity :size="18"/> Bình chọn</button>
          </section>

          <form class="feed-search input-with-icon" @submit.prevent="loadSocialPosts"><Search :size="17"/><input v-model="feedSearch" placeholder="Tìm bài viết hoặc hashtag…" aria-label="Tìm bài viết hoặc hashtag"/><button type="submit" class="soft-btn">Tìm bài</button><button v-if="feedSearch" type="button" class="icon-btn" aria-label="Xóa bộ lọc" @click="searchFeed('')"><X :size="16"/></button></form>
          <div class="feed-tabs">
            <button
              v-for="tab in feedTabs"
              :key="tab"
              :class="{active:feedFilter===tab}"
              @click="feedFilter=tab"
            >
              {{ tab }}
            </button>
          </div>

          <div v-if="socialError" class="error-banner social-error">
            <X :size="17"/><span>{{ socialError }}</span>
          </div>

          <div v-if="socialLoading" class="social-loading-list">
            <div v-for="n in 3" :key="n" class="social-skeleton card">
              <span></span><div><i></i><i></i><i></i></div>
            </div>
          </div>

          <div v-else-if="posts.length===0" class="empty-state premium">
            <div class="empty-orb"><MessageCircle :size="27"/></div>
            <h3>Chưa có bài viết trong mục này</h3>
            <p>Hãy trở thành người đầu tiên chia sẻ câu hỏi hoặc kinh nghiệm với cộng đồng.</p>
            <button class="primary-btn" @click="openCreatePost">
              <Plus :size="16"/> Viết bài đầu tiên
            </button>
          </div>

          <section v-else class="feed-list">
            <article v-for="post in posts" :key="post.id" class="post-card card">
              <div class="post-author">
                <span class="avatar" :class="{violet:post.verified}">
                  <img v-if="post.avatar" :src="post.avatar" alt=""/><template v-else>{{ post.initials }}</template>
                </span>

                <div>
                  <strong>
                    {{ post.author }}
                    <ShieldCheck
                      v-if="post.verified"
                      class="verified-icon"
                      :size="15"
                    />
                  </strong>
                  <small>
                    {{ post.role }} • {{ post.time }}
                  </small>
                </div>

                <span class="post-category-badge">
                  {{ post.categoryLabel }}
                </span>

                <div class="post-menu-wrap">
                  <button class="icon-btn" aria-label="Thao tác bài viết" @click="postMenu=postMenu===post.id?null:post.id"><MoreHorizontal :size="19"/></button>
                  <div v-if="postMenu===post.id" class="post-menu">
                    <button @click="sharePost(post);postMenu=null">Chia sẻ liên kết</button>
                    <button v-if="post.canEdit" @click="editingPost=post;editingContent=post.content;postMenu=null">Chỉnh sửa bài viết</button>
                    <button v-if="post.canEdit" class="danger-text" @click="deleteCandidate=post;postMenu=null">Xóa bài viết</button>
                  </div>
                </div>
              </div>

              <p class="post-content">
                {{ post.content }}
              </p>

              <PostAttachments :post="post" :user="currentUser" @login="openAuth('login')"/>
              <div v-if="post.tags.length" class="tag-row">
                <span
                  v-for="tag in post.tags"
                  :key="tag"
                >
                  {{ tag }}
                </span>
              </div>

              <div class="post-stats">
                <span>{{ post.likes }} lượt thích • {{ post.saves }} lượt lưu</span>
                <span>{{ post.comments }} bình luận</span>
              </div>

              <div class="post-actions">
                <button
                  :class="{liked:post.liked}"
                  :disabled="socialActionBusy[`like-${post.id}`]"
                  @click="likePost(post)"
                >
                  <ThumbsUp :size="18"/>
                  {{ post.liked ? 'Đã thích' : 'Thích' }}
                </button>

                <button
                  @click="toggleCommentBox(post.id)"
                >
                  <MessageCircle :size="18"/>
                  Bình luận
                </button>

                <button
                  @click="sharePost(post)"
                >
                  <Share2 :size="18"/>
                  Chia sẻ
                </button>

                <button
                  :class="{saved:post.saved}"
                  :disabled="socialActionBusy[`save-${post.id}`]"
                  @click="savePost(post)"
                >
                  <Bookmark :size="18"/>
                  {{ post.saved ? 'Đã lưu' : 'Lưu' }}
                </button>
              </div>

              <button v-if="post.comments>post.topComments.length" class="ghost-btn all-comments" @click="showAllComments(post)">Xem tất cả {{ post.comments }} bình luận</button>
              <div v-if="post.topComments?.length" class="comment-preview-list">
                <div
                  v-for="comment in post.topComments"
                  :key="comment.id"
                  class="top-comment"
                >
                  <span class="avatar tiny">
                    <img v-if="comment.avatar" :src="comment.avatar" alt=""/><template v-else>{{ comment.initials }}</template>
                  </span>

                  <div>
                    <strong>
                      {{ comment.author }}
                      <small>• {{ comment.time }}</small>
                    </strong>
                    <p>{{ comment.content }}</p>
                  </div>
                </div>
              </div>

              <div v-if="commentOpen[post.id]" class="comment-compose">
                <span class="avatar tiny">
                  {{ profile.initials }}
                </span>

                <input
                  v-model="commentDrafts[post.id]"
                  :placeholder="currentUser ? 'Viết bình luận...' : 'Đăng nhập để bình luận'"
                  @keyup.enter="submitComment(post)"
                />

                <button
                  :disabled="!String(commentDrafts[post.id]||'').trim() || socialActionBusy[`comment-${post.id}`]"
                  @click="submitComment(post)"
                >
                  <Send :size="15"/>
                </button>
              </div>
            </article>
          </section>
        </template>

        <template v-else-if="activeTab==='saved'">
          <section class="page-intro">
            <div>
              <span class="section-kicker">SAVED CENTER • DATABASE THẬT</span>
              <h1>Trường & nội dung đã lưu</h1>
              <p>Bookmark được gắn theo tài khoản và vẫn còn sau khi F5 hoặc đăng nhập lại.</p>
            </div>
          </section>

          <div v-if="!currentUser" class="empty-state premium">
            <div class="empty-orb"><Bookmark :size="27"/></div>
            <h3>Đăng nhập để xem nội dung đã lưu</h3>
            <p>Trường và bài viết đã lưu được gắn với tài khoản UniConnect AI của bạn.</p>
            <button class="primary-btn" @click="openAuth('login')">
              <CircleUserRound :size="16"/> Đăng nhập
            </button>
          </div>

          <template v-else>
            <div class="saved-tabs">
              <button
                :class="{active:savedSection==='schools'}"
                @click="savedSection='schools'"
              >
                <Building2 :size="16"/>
                Trường đã lưu
                <span>{{ savedUniversities.length }}</span>
              </button>

              <button
                :class="{active:savedSection==='posts'}"
                @click="savedSection='posts'"
              >
                <Bookmark :size="16"/>
                Bài viết đã lưu
                <span>{{ posts.length }}</span>
              </button>
            </div>

            <template v-if="savedSection==='schools'">
              <div
                v-if="savedUniversitiesError"
                class="error-banner"
              >
                <X :size="17"/>
                <span>{{ savedUniversitiesError }}</span>
              </div>

              <div
                v-if="savedUniversitiesLoading"
                class="results-skeleton"
              >
                <div
                  v-for="n in 3"
                  :key="n"
                  class="skeleton-card"
                >
                  <span></span>
                  <div><i></i><i></i><i></i></div>
                </div>
              </div>

              <div
                v-else-if="savedUniversities.length===0"
                class="empty-state premium"
              >
                <div class="empty-orb neutral">
                  <Building2 :size="27"/>
                </div>
                <h3>Bạn chưa lưu trường nào</h3>
                <p>Vào Khám phá trường hoặc kết quả AI Advisor và bấm biểu tượng bookmark.</p>
                <button
                  class="primary-btn"
                  @click="setTab('universities')"
                >
                  <Building2 :size="16"/>
                  Khám phá trường
                </button>
              </div>

              <section
                v-else
                class="saved-school-grid"
              >
                <article
                  v-for="school in savedUniversities"
                  :key="school.university_key"
                  class="saved-school-card card"
                >
                  <div
                    class="saved-school-cover"
                    :style="{background:school.accent}"
                  >
                    <span>{{ school.short }}</span>

                    <button
                      class="icon-btn light"
                      title="Bỏ lưu"
                      @click="toggleUniversitySave(school)"
                    >
                      <Bookmark :size="17" fill="currentColor"/>
                    </button>
                  </div>

                  <div class="saved-school-body">
                    <h3>{{ school.name }}</h3>

                    <p>
                      <MapPin :size="14"/>
                      {{ school.city || 'Chưa có metadata vị trí' }}
                    </p>

                    <div class="saved-school-stats">
                      <span>
                        <small>Ngành sạch</small>
                        <strong>{{ school.program_count }}</strong>
                      </span>

                      <span>
                        <small>Độ phủ</small>
                        <strong>{{ school.year_count }}/4 năm</strong>
                      </span>

                      <span>
                        <small>Khoảng điểm</small>
                        <strong>{{ Number(school.score_min).toFixed(2) }}–{{ Number(school.score_max).toFixed(2) }}</strong>
                      </span>
                    </div>

                    <div class="card-actions">
                      <button
                        class="primary-btn small"
                        @click="openUniversity(school)"
                      >
                        Xem 2023–2026
                      </button>

                      <button
                        class="ghost-btn"
                        @click="toggleCompare(school);goToCompare()"
                      >
                        <Target :size="15"/>
                        So sánh
                      </button>
                    </div>
                  </div>
                </article>
              </section>
            </template>

            <template v-else>
              <div
                v-if="socialError"
                class="error-banner social-error"
              >
                <X :size="17"/>
                <span>{{ socialError }}</span>
              </div>

              <div
                v-if="socialLoading"
                class="social-loading-list"
              >
                <div
                  v-for="n in 3"
                  :key="n"
                  class="social-skeleton card"
                >
                  <span></span>
                  <div><i></i><i></i><i></i></div>
                </div>
              </div>

              <div
                v-else-if="posts.length===0"
                class="empty-state premium"
              >
                <div class="empty-orb neutral">
                  <Bookmark :size="27"/>
                </div>
                <h3>Bạn chưa lưu bài viết nào</h3>
                <p>Vào Feed cộng đồng và bấm “Lưu” ở bài bạn muốn xem lại.</p>
                <button
                  class="primary-btn"
                  @click="setTab('social')"
                >
                  <LayoutDashboard :size="16"/>
                  Mở bảng tin
                </button>
              </div>

              <section
                v-else
                class="feed-list"
              >
                <article
                  v-for="post in posts"
                  :key="post.id"
                  class="post-card card"
                >
                  <div class="post-author">
                    <span class="avatar" :class="{violet:post.verified}">
                      <img v-if="post.avatar" :src="post.avatar" alt=""/><template v-else>{{ post.initials }}</template>
                    </span>

                    <div>
                      <strong>{{ post.author }}</strong>
                      <small>{{ post.role }} • {{ post.time }}</small>
                    </div>

                    <span class="post-category-badge">
                      {{ post.categoryLabel }}
                    </span>
                  </div>

                  <p class="post-content">{{ post.content }}</p>

                  <PostAttachments :post="post" :user="currentUser" @login="openAuth('login')"/>
              <div v-if="post.tags.length" class="tag-row">
                    <span
                      v-for="tag in post.tags"
                      :key="tag"
                    >
                      {{ tag }}
                    </span>
                  </div>

                  <div class="post-stats">
                    <span>{{ post.likes }} lượt thích</span>
                    <span>{{ post.comments }} bình luận • {{ post.saves }} lượt lưu</span>
                  </div>

                  <div class="post-actions">
                    <button
                      :class="{liked:post.liked}"
                      @click="likePost(post)"
                    >
                      <ThumbsUp :size="18"/>
                      {{ post.liked ? 'Đã thích' : 'Thích' }}
                    </button>

                    <button
                      @click="toggleCommentBox(post.id)"
                    >
                      <MessageCircle :size="18"/>
                      Bình luận
                    </button>

                    <button @click="sharePost(post)">
                      <Share2 :size="18"/>
                      Chia sẻ
                    </button>

                    <button
                      class="saved"
                      @click="savePost(post)"
                    >
                      <Bookmark :size="18"/>
                      Bỏ lưu
                    </button>
                  </div>

                  <div
                    v-if="post.topComments?.length"
                    class="comment-preview-list"
                  >
                    <div
                      v-for="comment in post.topComments"
                      :key="comment.id"
                      class="top-comment"
                    >
                      <span class="avatar tiny">
                        {{ comment.initials }}
                      </span>

                      <div>
                        <strong>
                          {{ comment.author }}
                          <small>• {{ comment.time }}</small>
                        </strong>
                        <p>{{ comment.content }}</p>
                      </div>
                    </div>
                  </div>
                </article>
              </section>
            </template>
          </template>
        </template>

        <template v-else-if="activeTab==='quiz'">
          <section class="page-intro">
            <div>
              <span class="section-kicker">HOLLAND-STYLE RIASEC • LƯU DATABASE</span>
              <h1>Khám phá nhóm sở thích nghề nghiệp</h1>
              <p>24 câu tự đánh giá theo 6 nhóm RIASEC. Kết quả được dùng để gợi ý ngành đang có trong dataset UniConnect AI.</p>
            </div>
            <button
              v-if="careerResult"
              class="soft-btn"
              @click="resetCareerQuiz"
            >
              <Activity :size="17"/> Làm lại
            </button>
          </section>

          <div v-if="careerError" class="error-banner career-error">
            <X :size="17"/><span>{{ careerError }}</span>
          </div>

          <div v-if="careerLoading" class="empty-state premium">
            <div class="empty-orb"><Lightbulb :size="27"/></div>
            <h3>Đang tải bộ câu hỏi RIASEC...</h3>
            <p>UniConnect AI đang chuẩn bị bài tự đánh giá hướng nghiệp.</p>
          </div>

          <template v-else-if="careerResult">
            <section class="career-result-hero card">
              <div class="career-code-block">
                <span class="section-kicker">MÃ HOLLAND CỦA BẠN</span>
                <strong>{{ careerResult.holland_code }}</strong>
                <p>Ba nhóm nổi bật nhất trong lần làm gần nhất.</p>
              </div>

              <div class="career-top-dimensions">
                <div
                  v-for="(dimension,index) in careerResult.top_dimensions"
                  :key="dimension.code"
                  class="career-top-card"
                >
                  <span class="career-rank">#{{ index + 1 }}</span>
                  <div>
                    <strong>{{ dimension.code }} • {{ dimension.label }}</strong>
                    <small>{{ dimension.description }}</small>
                  </div>
                  <b>{{ Number(dimension.percent).toFixed(0) }}%</b>
                </div>
              </div>
            </section>

            <section class="career-score-card card">
              <div class="section-heading compact">
                <div>
                  <span class="section-kicker">HỒ SƠ RIASEC</span>
                  <h2>Điểm theo 6 nhóm</h2>
                </div>
              </div>

              <div class="career-score-list">
                <div
                  v-for="code in ['R','I','A','S','E','C']"
                  :key="code"
                  class="career-score-row"
                >
                  <span class="career-score-code">{{ code }}</span>

                  <div class="career-score-main">
                    <div>
                      <strong>{{ careerResult.scores[code]?.label }}</strong>
                      <span>{{ careerResult.scores[code]?.name }}</span>
                    </div>

                    <div class="career-score-track">
                      <i
                        :style="{width:`${careerResult.scores[code]?.percent || 0}%`}"
                      ></i>
                    </div>
                  </div>

                  <b>{{ Number(careerResult.scores[code]?.percent || 0).toFixed(0) }}%</b>
                </div>
              </div>
            </section>

            <section class="career-major-section card">
              <div class="section-heading">
                <div>
                  <span class="section-kicker">GỢI Ý TỪ DATASET THẬT</span>
                  <h2>Ngành nên khám phá tiếp</h2>
                  <p>Danh sách này được đối chiếu với tên ngành thực tế trong dataset 2023–2026, không phải danh sách ngành viết sẵn ở frontend.</p>
                </div>
              </div>

              <div v-if="careerResult.suggested_majors?.length" class="career-major-grid">
                <article
                  v-for="major in careerResult.suggested_majors"
                  :key="`${major.major_code}-${major.major_name}`"
                  class="career-major-card"
                >
                  <div class="career-major-icon">
                    <GraduationCap :size="19"/>
                  </div>

                  <div>
                    <strong>{{ major.major_name }}</strong>
                    <span>{{ major.major_code }}</span>
                    <small>
                      Có tại {{ major.schools_count }} trường •
                      phù hợp nhóm {{ major.matched_dimensions.join(' + ') }}
                    </small>
                  </div>

                  <button
                    class="soft-btn"
                    @click="useCareerMajor(major)"
                  >
                    Dùng cho AI Advisor
                  </button>
                </article>
              </div>

              <div v-else class="compare-hint">
                <Search :size="18"/>
                <span>Chưa tìm được ngành khớp đủ rõ trong dataset hiện tại.</span>
              </div>
            </section>

            <section class="career-disclaimer">
              <ShieldCheck :size="16"/>
              <span>
                {{ careerResult.disclaimer || careerDisclaimer }}
                Kết quả nhằm hỗ trợ khám phá ngành, không phải kết luận năng lực hay chẩn đoán tâm lý.
              </span>
            </section>
          </template>

          <template v-else>
            <section class="career-progress-card card">
              <div class="career-progress-head">
                <div>
                  <span class="section-kicker">TIẾN ĐỘ</span>
                  <strong>{{ careerAnsweredCount }}/{{ careerQuestions.length }} câu</strong>
                </div>
                <span>{{ careerProgress }}%</span>
              </div>

              <div class="career-progress-track">
                <i :style="{width:`${careerProgress}%`}"></i>
              </div>
            </section>

            <section
              v-if="careerCurrentQuestion"
              class="career-question-card card"
            >
              <div class="career-question-meta">
                <span>
                  Câu {{ careerIndex + 1 }} / {{ careerQuestions.length }}
                </span>
                <span>
                  {{ careerDimensions[careerCurrentQuestion.dimension]?.label }}
                </span>
              </div>

              <h2>{{ careerCurrentQuestion.text }}</h2>

              <div class="career-scale">
                <button
                  v-for="score in [1,2,3,4,5]"
                  :key="score"
                  :class="{selected:careerAnswers[careerCurrentQuestion.id]===score}"
                  @click="answerCareer(careerCurrentQuestion.id,score)"
                >
                  <strong>{{ score }}</strong>
                  <span>{{ careerScale.labels?.[String(score)] }}</span>
                </button>
              </div>

              <div class="career-navigation">
                <button
                  class="ghost-btn"
                  :disabled="careerIndex===0"
                  @click="previousCareerQuestion"
                >
                  ← Câu trước
                </button>

                <div class="career-question-dots">
                  <span
                    v-for="question in careerQuestions"
                    :key="question.id"
                    :class="{
                      answered:careerAnswers[question.id]!==undefined,
                      current:question.id===careerCurrentQuestion.id
                    }"
                  ></span>
                </div>

                <button
                  v-if="careerIndex < careerQuestions.length-1"
                  class="primary-btn"
                  :disabled="careerAnswers[careerCurrentQuestion.id]===undefined"
                  @click="nextCareerQuestion"
                >
                  Câu tiếp →
                </button>

                <button
                  v-else
                  class="primary-btn"
                  :disabled="careerAnsweredCount!==careerQuestions.length || careerSubmitting"
                  @click="submitCareerQuiz"
                >
                  <span v-if="careerSubmitting" class="spinner"></span>
                  <Sparkles v-else :size="16"/>
                  {{ careerSubmitting ? 'Đang phân tích...' : 'Xem kết quả' }}
                </button>
              </div>
            </section>

            <section
              v-if="careerHistory.length"
              class="career-history card"
            >
              <div class="widget-head">
                <span><Clock3 :size="18"/> Lịch sử gần đây</span>
              </div>

              <div class="career-history-list">
                <button
                  v-for="item in careerHistory.slice(0,5)"
                  :key="item.id"
                  class="career-history-item"
                  @click="openCareerHistory(item)"
                >
                  <span class="career-history-code">{{ item.holland_code }}</span>

                  <span class="career-history-copy">
                    <strong>RIASEC</strong>
                    <small>{{ new Date(item.created_at).toLocaleString('vi-VN') }}</small>
                  </span>

                  <span class="career-history-view">
                    Xem kết quả →
                  </span>
                </button>
              </div>
            </section>

            <section class="career-disclaimer">
              <ShieldCheck :size="16"/>
              <span>{{ careerDisclaimer }}</span>
            </section>
          </template>
        </template>

        <template v-else-if="activeTab==='compare'">
          <section class="page-intro">
            <div>
              <span class="section-kicker">SCHOOL COMPARISON • REAL DATA</span>
              <h1>So sánh 2–3 trường cạnh nhau</h1>
              <p>Dùng dữ liệu program-year sạch 2023–2026 để đối chiếu độ phủ dữ liệu, khoảng điểm và lịch sử ngành.</p>
            </div>
            <button class="soft-btn" @click="setTab('universities')">
              <Building2 :size="17"/> Thêm từ Khám phá trường
            </button>
          </section>

          <section class="compare-control card">
            <div class="compare-add-row">
              <div>
                <span class="section-kicker">DANH SÁCH SO SÁNH</span>
                <strong>{{ compareList.length }}/3 trường đã chọn</strong>
              </div>

              <div class="compare-add-actions">
                <select
                  v-model="compareAddKey"
                  class="toolbar-select"
                  :disabled="compareList.length>=3"
                >
                  <option value="">Chọn thêm trường...</option>
                  <option
                    v-for="school in compareAvailableSchools"
                    :key="school.id"
                    :value="school.id"
                  >
                    {{ school.name }}
                  </option>
                </select>

                <button
                  class="primary-btn small"
                  :disabled="!compareAddKey || compareList.length>=3"
                  @click="addCompareSchool"
                >
                  <Plus :size="15"/> Thêm
                </button>
              </div>
            </div>

            <div v-if="compareList.length" class="compare-selected-list">
              <div
                v-for="school in compareList"
                :key="school.id"
                class="compare-selected-chip"
              >
                <span
                  class="compare-chip-logo"
                  :style="{background:school.accent}"
                >
                  {{ school.short }}
                </span>

                <span>
                  <strong>{{ school.name }}</strong>
                  <small>{{ school.city || 'Chưa có metadata vị trí' }}</small>
                </span>

                <button
                  class="icon-btn"
                  @click="removeCompareSchool(school)"
                >
                  <X :size="16"/>
                </button>
              </div>
            </div>
          </section>

          <div v-if="compareError" class="error-banner compare-error">
            <X :size="17"/><span>{{ compareError }}</span>
          </div>

          <div v-if="compareList.length<2" class="empty-state premium">
            <div class="empty-orb"><Target :size="27"/></div>
            <h3>Chọn ít nhất 2 trường để so sánh</h3>
            <p>Bạn có thể chọn trường ngay tại đây hoặc vào mục “Khám phá trường” rồi bấm “So sánh”.</p>
            <button class="primary-btn" @click="setTab('universities')">
              <Building2 :size="16"/> Chọn trường
            </button>
          </div>

          <div v-else-if="compareLoading" class="results-skeleton">
            <div v-for="n in compareList.length" :key="n" class="skeleton-card">
              <span></span><div><i></i><i></i><i></i></div>
            </div>
          </div>

          <template v-else>
            <section class="compare-grid">
              <article
                v-for="school in compareList"
                :key="school.id"
                class="compare-school-card card"
              >
                <div
                  class="compare-school-cover"
                  :style="{background:school.accent}"
                >
                  <span>{{ school.short }}</span>
                  <ShieldCheck :size="18"/>
                </div>

                <div class="compare-school-body">
                  <h3>{{ school.name }}</h3>
                  <p><MapPin :size="14"/> {{ compareDetails[school.id]?.city || school.city || 'Chưa có metadata' }}</p>

                  <div class="compare-stat-grid">
                    <div>
                      <small>Số ngành sạch</small>
                      <strong>{{ compareDetails[school.id]?.program_count ?? school.program_count }}</strong>
                    </div>
                    <div>
                      <small>Năm có dữ liệu</small>
                      <strong>{{ (compareDetails[school.id]?.available_years || school.available_years || []).length }}/4</strong>
                    </div>
                    <div>
                      <small>Điểm thấp nhất</small>
                      <strong>{{ Number(compareDetails[school.id]?.score_min ?? school.score_min).toFixed(2) }}</strong>
                    </div>
                    <div>
                      <small>Điểm cao nhất</small>
                      <strong>{{ Number(compareDetails[school.id]?.score_max ?? school.score_max).toFixed(2) }}</strong>
                    </div>
                  </div>

                  <div class="year-coverage">
                    <span
                      v-for="year in [2023,2024,2025,2026]"
                      :key="year"
                      :class="{available:(compareDetails[school.id]?.available_years || []).includes(year)}"
                    >
                      {{ year }}
                    </span>
                  </div>
                </div>
              </article>
            </section>

            <section class="compare-program-section card">
              <div class="section-heading">
                <div>
                  <span class="section-kicker">SO SÁNH THEO NGÀNH</span>
                  <h2>Tìm cùng một ngành giữa các trường</h2>
                  <p>Nhập tên ngành hoặc mã ngành. Mỗi trường hiển thị lịch sử 2023–2026 của các chương trình khớp.</p>
                </div>
              </div>

              <div class="input-with-icon compare-major-search">
                <Search :size="17"/>
                <input
                  v-model="compareMajorQuery"
                  placeholder="VD: Công nghệ thông tin hoặc 7480201"
                />
              </div>

              <div v-if="!compareMajorQuery.trim()" class="compare-hint">
                <Target :size="18"/>
                <span>Nhập ngành hoặc mã ngành để bắt đầu đối chiếu.</span>
              </div>

              <div v-else class="compare-program-columns">
                <div
                  v-for="column in compareProgramResults"
                  :key="column.school.id"
                  class="compare-program-column"
                >
                  <div class="compare-column-head">
                    <span
                      class="compare-mini-logo"
                      :style="{background:column.school.accent}"
                    >
                      {{ column.school.short }}
                    </span>

                    <strong>{{ column.school.name }}</strong>
                  </div>

                  <div v-if="column.programs.length===0" class="compare-no-program">
                    Không tìm thấy ngành khớp trong dataset sạch.
                  </div>

                  <article
                    v-for="program in column.programs"
                    :key="program.program_key"
                    class="compare-program-card"
                  >
                    <div>
                      <strong>{{ program.major_name }}</strong>
                      <span>{{ program.major_code }}</span>
                    </div>

                    <div class="compare-year-grid">
                      <div v-for="year in [2023,2024,2025,2026]" :key="year">
                        <small>{{ year }}</small>
                        <strong>{{ compareYearScore(column.detail, program, year) }}</strong>
                      </div>
                    </div>
                  </article>
                </div>
              </div>
            </section>
          </template>
        </template>

        <template v-else>
          <section class="page-intro">
            <div><span class="section-kicker">UNIVERSITY DISCOVERY</span><h1>Khám phá trường đại học</h1><p>Lọc theo khu vực và lưu các trường bạn muốn nghiên cứu sâu hơn.</p></div>
            <button class="soft-btn"><Settings2 :size="17"/> Bộ lọc nâng cao</button>
          </section>
          <section class="discovery-toolbar card">
            <div class="input-with-icon discovery-search"><Search :size="17"/><input v-model="searchQuery" placeholder="Tìm theo tên trường..."/></div>
            <select v-model="discoveryCity" class="toolbar-select"><option value="Tất cả">Tất cả khu vực</option><option v-for="city in cityOptions" :key="city">{{ city }}</option></select>
            <button class="compare-status compare-status-btn" @click="goToCompare">
              <Target :size="16"/> So sánh {{ compareList.length }}/3
            </button>
          </section>
          <div v-if="catalogLoading" class="empty-state premium">
            <div class="empty-orb"><Building2 :size="27"/></div>
            <h3>Đang tải cơ sở dữ liệu trường...</h3>
            <p>UniConnect AI đang đọc dataset program-year 2023–2026.</p>
          </div>

          <div v-else-if="catalogError" class="error-banner">
            <X :size="17"/><span>{{ catalogError }}</span>
          </div>

          <section v-else class="university-grid">
            <article v-for="university in filteredUniversities" :key="university.id" class="university-card card">
              <div class="university-cover" :style="{background:university.accent}"><span>{{ university.short }}</span><Sparkles :size="20"/></div>
              <div class="university-body">
                <div class="university-title">
                  <div>
                    <h3>{{ university.name }}</h3>
                    <span><MapPin :size="14"/> {{ university.city }}</span>
                  </div>

                  <button
                    class="icon-btn university-save-btn"
                    :class="{saved:university.saved}"
                    :disabled="savingUniversity[university.university_key]"
                    :title="university.saved ? 'Bỏ lưu trường' : 'Lưu trường'"
                    @click.stop="toggleUniversitySave(university)"
                  >
                    <Bookmark
                      :size="18"
                      :fill="university.saved ? 'currentColor' : 'none'"
                    />
                  </button>
                </div>
                <div class="rating-line real-data-line"><ShieldCheck :size="15"/><strong>{{ university.year_count }}/4 năm</strong><span>• {{ university.program_count }} ngành sạch</span></div>
                <p>{{ university.field }}</p>
                <div class="university-info">
                  <span><b>Khoảng điểm dữ liệu</b>{{ Number(university.score_min).toFixed(2) }} – {{ Number(university.score_max).toFixed(2) }}</span>
                  <span><b>Vị trí</b>{{ university.verified ? university.city : 'Chưa có metadata' }}</span>
                </div>
                <div class="card-actions"><button class="primary-btn small" @click="openUniversity(university)">Xem chi tiết</button><button class="ghost-btn" :class="{selected:compareList.some(u=>u.id===university.id)}" @click="toggleCompare(university)"><Target :size="15"/> {{ compareList.some(u=>u.id===university.id)?'Đã chọn':'So sánh' }}</button></div>
              </div>
            </article>
          </section>
        </template>
      </main>

      <aside class="right-sidebar">
        <section class="utility-card card">
          <div class="widget-head"><span><Building2 :size="18"/> Trường trong khu vực</span><button @click="setTab('universities')">Xem tất cả</button></div>
          <div class="trend-list"><button v-for="item in trends" :key="item.id" class="trend-item" @click="openUniversity(item)"><span class="rank">{{ item.rank }}</span><div><strong>{{ item.name }}</strong><small>{{ item.searches }}</small></div><span class="trend-delta">↗</span></button></div>
        </section>

        <section class="utility-card card">
          <div class="widget-head">
            <span><Users :size="18"/> Mentor / Kết nối</span>
            <button @click="loadMentorSuggestions">Làm mới</button>
          </div>

          <div v-if="mentorLoading" class="mentor-empty">
            Đang tải gợi ý...
          </div>

          <div v-else-if="mentorError" class="mentor-empty error-text">
            {{ mentorError }}
          </div>

          <div v-else-if="mentorSuggestions.length===0" class="mentor-empty">
            Chưa có gợi ý kết nối lúc này. Bạn có thể làm quen với các thành viên qua bài viết cộng đồng nhé.
          </div>

          <div v-else class="mentor-list">
            <div
              v-for="mentor in mentorSuggestions.slice(0,4)"
              :key="mentor.id"
              class="mentor-item"
            >
              <span class="avatar mini violet"><img v-if="mentor.avatar_url" :src="mentor.avatar_url" alt=""/><template v-else>{{ mentor.initials }}</template></span>

              <div>
                <strong>
                  {{ mentor.name }}
                  <ShieldCheck
                    v-if="mentor.isMentor"
                    :size="12"
                    class="verified-icon"
                  />
                </strong>
                <small>
                  {{ mentor.role }}
                  <template v-if="mentor.city"> • {{ mentor.city }}</template>
                </small>
              </div>

              <button
                :class="{connected:mentor.following}"
                :disabled="connectionBusy[mentor.id]"
                @click="toggleMentorConnection(mentor)"
              >
                {{ mentor.following ? 'Đã kết nối' : 'Kết nối' }}
              </button>
            </div>
          </div>
        </section>

        <section class="countdown-card">
          <div class="countdown-head"><Clock3 :size="18"/><span><strong>Mốc ôn tập THPT 2027</strong><small>25/06/2027 • mốc demo, cập nhật khi có lịch chính thức</small></span></div>
          <div class="countdown-grid"><div><strong>{{ countdown.days }}</strong><small>Ngày</small></div><div><strong>{{ countdown.hours }}</strong><small>Giờ</small></div><div><strong>{{ countdown.minutes }}</strong><small>Phút</small></div><div><strong>{{ countdown.seconds }}</strong><small>Giây</small></div></div>
        </section>

        <section class="utility-card card">
          <div class="widget-head"><span><Hash :size="18"/> Hashtag nổi bật</span></div>
          <div class="hashtag-cloud"><button v-for="tag in hashtags" :key="tag" @click="searchFeed(tag)">{{ tag }}</button></div>
        </section>
        <div class="sidebar-footnote">UniConnect AI • Dữ liệu tư vấn 2023–2026 • Target 2027</div>
      </aside>
    </div>

    <div v-if="toast" class="app-toast" role="status">{{ toast }}</div>
    <div v-if="editingPost" class="modal-backdrop" @click.self="editingPost=null"><section class="standard-modal"><div class="modal-head"><h3>Chỉnh sửa bài viết</h3><button class="icon-btn" @click="editingPost=null" aria-label="Đóng">×</button></div><textarea v-model="editingContent" maxlength="3000" rows="7"/><button class="primary-btn full" :disabled="!editingContent.trim()" @click="editPost">Lưu thay đổi</button></section></div>
    <div v-if="deleteCandidate" class="modal-backdrop" @click.self="deleteCandidate=null"><section class="standard-modal"><h3>Xóa bài viết của bạn?</h3><p>Bài viết, ảnh và các bình luận liên quan sẽ bị xóa.</p><div class="confirm-actions"><button class="ghost-btn" @click="deleteCandidate=null">Giữ bài viết</button><button class="primary-btn danger" @click="deletePost">Xóa bài viết</button></div></section></div>
    <div v-if="searchOpen" class="modal-backdrop" @click.self="searchOpen=false">
      <div class="search-modal">
        <div class="search-modal-input"><Search :size="20"/><input v-model="searchQuery" autofocus placeholder="Tìm trường, mã ngành, bài viết, hashtag..."/><button class="icon-btn" @click="searchOpen=false"><X :size="19"/></button></div>
        <div class="search-hint"><span>Tìm kiếm realtime</span><kbd>ESC</kbd></div>
        <div class="search-result-list">
          <button v-for="item in searchResults" :key="`${item.type}-${item.title}`" @click="item.action()"><span class="search-type">{{ item.type }}</span><span><strong>{{ item.title }}</strong><small>{{ item.subtitle }}</small></span><span class="arrow">↗</span></button>
          <div v-if="searchResults.length===0" class="no-search-result">Không tìm thấy kết quả phù hợp.</div>
        </div>
      </div>
    </div>

    <div v-if="creatingPost" class="modal-backdrop" @click.self="creatingPost=false">
      <div class="standard-modal">
        <div class="modal-head"><div><span class="section-kicker">EDUSOCIAL</span><h3>Tạo bài viết mới</h3></div><button class="icon-btn" @click="creatingPost=false"><X :size="19"/></button></div>
        <div class="author-inline"><span class="avatar"><img v-if="currentUser?.avatar_url" :src="currentUser.avatar_url" alt="Ảnh đại diện của bạn"/><template v-else>{{ profile.initials }}</template></span><div><strong>{{ profile.name }}</strong><small>Cộng đồng UniConnect AI</small></div></div>
        <textarea v-model="newPost" maxlength="3000" rows="6" placeholder="Chia sẻ câu hỏi, trải nghiệm hoặc kinh nghiệm chọn trường..."></textarea>
        <div class="post-compose-tools">
          <select v-model="newPostCategory">
            <option v-for="item in postCategoryOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="newPostTag">
            <option v-for="tag in hashtags" :key="tag">{{ tag }}</option>
          </select>
          <button type="button" @click="imageInput.click()"><ImageIcon :size="17"/> Thêm ảnh</button>
          <button type="button" @click="pollEnabled=!pollEnabled"><Activity :size="17"/> {{ pollEnabled ? 'Bỏ bình chọn' : 'Tạo bình chọn' }}</button>
        </div>
        <input ref="imageInput" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden @change="chooseImages"/>
        <div v-if="postImages.length" class="compose-images"><div v-for="(image,index) in postImages" :key="image.url"><img :src="image.url" alt="Ảnh đang chọn"/><button @click="removeImage(index)" aria-label="Bỏ ảnh">×</button></div></div>
        <div v-if="pollEnabled" class="poll-editor"><strong>Bình chọn cộng đồng</strong><label v-for="(_,index) in pollDraft" :key="index"><input v-model="pollDraft[index]" maxlength="120" :placeholder="`Lựa chọn ${index+1}`"/><button v-if="pollDraft.length>2" class="icon-btn" @click="pollDraft.splice(index,1)" aria-label="Bỏ lựa chọn">×</button></label><button v-if="pollDraft.length<6" class="ghost-btn" @click="pollDraft.push('')">+ Thêm lựa chọn</button></div>
        <small class="compose-count">{{ newPost.length }}/3000 ký tự · Tối đa 4 ảnh, 5 MB/ảnh</small>
        <p v-if="composerError" role="alert" class="form-error">{{ composerError }}</p>
        <button class="primary-btn full" :disabled="!newPost.trim() || newPost.length>3000 || socialActionBusy.createPost" @click="publishPost">
          <span v-if="socialActionBusy.createPost" class="spinner"></span>
          <Send v-else :size="17"/>
          {{ socialActionBusy.createPost ? 'Đang đăng...' : 'Đăng bài' }}
        </button>
      </div>
    </div>

    <div v-if="universityModal" class="modal-backdrop" @click.self="universityModal=null">
      <div class="university-modal school-history-modal">
        <div class="university-modal-cover" :style="{background:universityModal.accent||'linear-gradient(135deg,#4F46E5,#8B5CF6)'}">
          <div>
            <span class="modal-school-mark">{{ universityModal.short||schoolShort(universityModal.name) }}</span>
            <div class="modal-cover-copy">
              <span>LỊCH SỬ ĐIỂM CHUẨN 2023–2026</span>
              <strong>{{ universityModal.name }}</strong>
            </div>
          </div>
          <button class="icon-btn light" @click="universityModal=null"><X :size="20"/></button>
        </div>

        <div class="university-modal-body school-history-body">
          <div class="school-meta-row">
            <span><MapPin :size="15"/> {{ schoolDetail?.city || universityModal.city || 'Chưa có metadata vị trí' }}</span>
            <span v-if="schoolDetail?.address">{{ schoolDetail.address }}</span>
          </div>

          <div v-if="schoolDetailLoading" class="school-detail-loading">
            <span class="spinner purple-spinner"></span>
            <strong>Đang tải lịch sử 2023–2026...</strong>
          </div>

          <div v-else-if="schoolDetail?.error" class="error-banner">
            <X :size="17"/><span>{{ schoolDetail.error }}</span>
          </div>

          <template v-else-if="schoolDetail">
            <div class="school-stat-strip">
              <div><small>Số ngành</small><strong>{{ schoolDetail.program_count }}</strong></div>
              <div><small>Năm có dữ liệu</small><strong>{{ schoolDetail.available_years.join(', ') }}</strong></div>
              <div><small>Điểm thấp nhất</small><strong>{{ Number(schoolDetail.score_min).toFixed(2) }}</strong></div>
              <div><small>Điểm cao nhất</small><strong>{{ Number(schoolDetail.score_max).toFixed(2) }}</strong></div>
            </div>

            <div class="history-scope-note">
              <ShieldCheck :size="16"/>
              <span>
                Đây là lịch sử <strong>điểm chuẩn THPT sạch/comparable dùng cho AI</strong>.
                Ô “—” nghĩa là dataset sạch không có dữ liệu năm đó; hệ thống không tự suy diễn.
              </span>
            </div>

            <div class="school-program-toolbar">
              <div class="input-with-icon">
                <Search :size="16"/>
                <input v-model="schoolProgramQuery" placeholder="Tìm mã ngành hoặc tên ngành..."/>
              </div>
              <span>{{ filteredSchoolPrograms.length }} ngành</span>
            </div>

            <div class="history-table-wrap">
              <table class="history-table">
                <thead>
                  <tr>
                    <th>Ngành / Mã</th>
                    <th>2023</th>
                    <th>2024</th>
                    <th>2025</th>
                    <th>2026</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="program in filteredSchoolPrograms" :key="program.program_key">
                    <td class="program-name-cell">
                      <strong>{{ program.major_name }}</strong>
                      <span>{{ program.major_code }}</span>
                    </td>
                    <td v-for="year in [2023,2024,2025,2026]" :key="year">
                      <template v-if="program.history[String(year)]">
                        <strong class="cutoff-value">{{ Number(program.history[String(year)].cutoff_score).toFixed(2) }}</strong>
                        <small>{{ program.history[String(year)].eligible_combinations || 'UNSPECIFIED' }}</small>
                      </template>
                      <span v-else class="missing-year">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <section v-if="schoolDetail.official_methods?.length" class="official-methods card">
              <h3>Điểm công bố theo từng phương thức</h3>
              <p>Xem đúng năm, phương thức và cách tính trong thông báo của trường.</p>
              <div v-for="row in schoolDetail.official_methods.filter(r=>!schoolProgramQuery || normalize(r.major_name+' '+r.major_code).includes(normalize(schoolProgramQuery)))" :key="`${row.major_code}-${row.major_name}-${row.year}-${row.admission_method}`" class="official-method-row">
                <div><strong>{{ row.major_name }}</strong><small>{{ row.year }} · {{ row.major_code || 'Chưa xác minh mã ngành' }} · {{ row.admission_method }}</small></div><div><b>{{ Number(row.cutoff_score).toFixed(2) }}</b><a :href="row.source_url" target="_blank" rel="noopener noreferrer">Nguồn ↗</a></div>
              </div>
            </section>
            <div class="school-detail-footer">
              <span>
                <ShieldCheck :size="14"/>
                Nguồn gốc từng program-year vẫn được giữ trong dataset.
              </span>

              <div class="school-detail-actions">
                <button
                  class="soft-btn"
                  :class="{selected:isUniversitySaved(universityModal)}"
                  @click="toggleUniversitySave(universityModal)"
                >
                  <Bookmark
                    :size="15"
                    :fill="isUniversitySaved(universityModal) ? 'currentColor' : 'none'"
                  />
                  {{ isUniversitySaved(universityModal) ? 'Đã lưu' : 'Lưu trường' }}
                </button>

                <button class="primary-btn" @click="form.city=schoolDetail.city||form.city;universityModal=null;setTab('advisor')">
                  <Bot :size="16"/> Tư vấn AI với trường này
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>

    <AuthModal
      v-model="authOpen"
      :initial-mode="authMode"
      @authenticated="onAuthenticated"
    />

    <ProfileModal
      v-model="profileEditorOpen"
      :user="currentUser"
      @updated="onProfileUpdated"
    />

    <div v-if="mobileMenu" class="mobile-overlay" @click="mobileMenu=false"></div>
  </div>
</template>
