import req from '@/utils/req'


export function listExpProfiles() {
  return req({
    url: '/exp/profiles',
    method: 'get'
  })
}

export function compareExp(expIds) {
  return req({
    url: '/exp/compare',
    method: 'get',
    params: {
      exp_ids: Array.isArray(expIds) ? expIds.join(',') : String(expIds || '')
    }
  })
}

export function listExp() {
  return req({
    url: '/exp',
    method: 'get'
  })
}

export function createExp(data) {
  return req({
    url: '/exp',
    method: 'post',
    data
  })
}

export function getExpDetail(expId) {
  return req({
    url: `/exp/${expId}`,
    method: 'get'
  })
}

export function startExp(expId) {
  return req({
    url: `/exp/${expId}/start`,
    method: 'post'
  })
}

export function stopExp(expId) {
  return req({
    url: `/exp/${expId}/stop`,
    method: 'post'
  })
}

export function getExpItems(expId) {
  return req({
    url: `/exp/${expId}/item`,
    method: 'get'
  })
}

export function getExpReport(expId) {
  return req({
    url: `/exp/${expId}/report`,
    method: 'get'
  })
}

export function getExpChart(expId) {
  return req({
    url: `/exp/${expId}/chart`,
    method: 'get'
  })
}


export function deleteExp(expId) {
  return req({
    url: `/exp/${expId}`,
    method: 'delete'
  })
}
