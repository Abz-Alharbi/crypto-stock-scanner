import { describe, it, expect, beforeEach, vi } from 'vitest'

const apiMocks = vi.hoisted(() => {
  const state = {
    unauthorizedHandler: null,
    authAPI: {
      login: vi.fn(),
      register: vi.fn(),
      me: vi.fn(),
      changePassword: vi.fn(),
    },
    setUnauthorizedHandler: vi.fn((handler) => {
      state.unauthorizedHandler = handler
    }),
  }
  return state
})

vi.mock('../services/api', () => ({
  authAPI: apiMocks.authAPI,
  setUnauthorizedHandler: apiMocks.setUnauthorizedHandler,
}))

import useAuthStore from './useAuthStore'

const resetAuthStore = () => {
  useAuthStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
    showAuthModal: false,
    authMode: 'login',
  })
}

describe('auth store', () => {
  beforeEach(() => {
    resetAuthStore()
  })

  it('logs in and stores the access token', async () => {
    apiMocks.authAPI.login.mockResolvedValueOnce({
      data: {
        token: 'token-1',
        user: { id: 1, username: 'aziz', email: 'aziz@example.test', role: 'user' },
      },
    })

    const user = await useAuthStore.getState().login('aziz@example.test', 'Password123')

    expect(apiMocks.authAPI.login).toHaveBeenCalledWith({
      email: 'aziz@example.test',
      password: 'Password123',
    })
    expect(user.username).toBe('aziz')
    expect(localStorage.getItem('access_token')).toBe('token-1')
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })

  it('registers and accepts access_token responses', async () => {
    apiMocks.authAPI.register.mockResolvedValueOnce({
      data: {
        access_token: 'registered-token',
        user: { id: 2, username: 'new_user', email: 'new@example.test', role: 'user' },
      },
    })

    await useAuthStore.getState().register('new_user', 'new@example.test', 'Password123')

    expect(apiMocks.authAPI.register).toHaveBeenCalledWith({
      username: 'new_user',
      email: 'new@example.test',
      password: 'Password123',
    })
    expect(localStorage.getItem('access_token')).toBe('registered-token')
    expect(JSON.parse(localStorage.getItem('auth_user')).email).toBe('new@example.test')
  })

  it('opens the login modal when the API reports unauthorized', () => {
    useAuthStore.setState({
      user: { id: 1, username: 'aziz' },
      token: 'expired',
      isAuthenticated: true,
    })

    apiMocks.unauthorizedHandler()

    expect(useAuthStore.getState()).toMatchObject({
      user: null,
      token: null,
      isAuthenticated: false,
      showAuthModal: true,
      authMode: 'login',
    })
  })
})

