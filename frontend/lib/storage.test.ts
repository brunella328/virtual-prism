import { describe, it, expect, beforeEach } from 'vitest'
import { storage } from './storage'

// jsdom 提供 localStorage mock，每個 test 清空一次
beforeEach(() => {
  localStorage.clear()
})

describe('storage.getUserId / setUserId', () => {
  it('returns null when not set', () => {
    expect(storage.getUserId()).toBeNull()
  })

  it('returns value after setUserId', () => {
    storage.setUserId('12345678')
    expect(storage.getUserId()).toBe('12345678')
  })
})

describe('storage.getIgUsername / setIgUsername', () => {
  it('returns null when not set', () => {
    expect(storage.getIgUsername()).toBeNull()
  })

  it('returns value after setIgUsername', () => {
    storage.setIgUsername('test_user')
    expect(storage.getIgUsername()).toBe('test_user')
  })
})

describe('storage.getAppearancePrompt / setAppearancePrompt', () => {
  it('returns empty string when not set', () => {
    expect(storage.getAppearancePrompt()).toBe('')
  })

  it('returns value after setAppearancePrompt', () => {
    storage.setAppearancePrompt('young woman, realistic')
    expect(storage.getAppearancePrompt()).toBe('young woman, realistic')
  })
})

describe('storage.getSchedule / setSchedule / clearSchedule', () => {
  it('returns null when not set', () => {
    expect(storage.getSchedule()).toBeNull()
  })

  it('returns parsed array after setSchedule', () => {
    const posts = [{ day: 1, scene: 'cafe' }, { day: 2, scene: 'park' }]
    storage.setSchedule(posts)
    expect(storage.getSchedule()).toEqual(posts)
  })

  it('returns null after clearSchedule', () => {
    storage.setSchedule([{ day: 1 }])
    storage.clearSchedule()
    expect(storage.getSchedule()).toBeNull()
  })

  it('returns null on corrupted JSON', () => {
    localStorage.setItem('vp_schedule', '{not valid json')
    expect(storage.getSchedule()).toBeNull()
  })

  it('returns null when stored value is not an array', () => {
    localStorage.setItem('vp_schedule', '{"key":"value"}')
    expect(storage.getSchedule()).toBeNull()
  })
})

describe('storage.clearAll', () => {
  it('removes all vp_* keys', () => {
    storage.setUserId('abc')
    storage.setIgUsername('user')
    storage.setAppearancePrompt('prompt')
    storage.setSchedule([{ day: 1 }])

    storage.clearAll()

    expect(storage.getUserId()).toBeNull()
    expect(storage.getIgUsername()).toBeNull()
    expect(storage.getAppearancePrompt()).toBe('')
    expect(storage.getSchedule()).toBeNull()
  })

  it('does not throw when storage is already empty', () => {
    expect(() => storage.clearAll()).not.toThrow()
  })
})
