import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const apiMocks = vi.hoisted(() => ({
  adminAPI: {
    getStats: vi.fn(),
    getUsers: vi.fn(),
    getScans: vi.fn(),
    getAuditLogs: vi.fn(),
    updateUser: vi.fn(),
  },
  authAPI: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    changePassword: vi.fn(),
  },
  setUnauthorizedHandler: vi.fn(),
}))

vi.mock('../../services/api', () => ({
  adminAPI: apiMocks.adminAPI,
  authAPI: apiMocks.authAPI,
  setUnauthorizedHandler: apiMocks.setUnauthorizedHandler,
}))

import AdminPanel from './AdminPanel'
import useAuthStore from '../../store/useAuthStore'

describe('AdminTable', () => {
  beforeEach(() => {
    Object.values(apiMocks.adminAPI).forEach((mock) => mock.mockReset())
    useAuthStore.setState({
      user: { id: 99, username: 'admin', email: 'admin@example.test', role: 'admin', plan: 'premium' },
      token: 'admin-token',
      isAuthenticated: true,
    })
    apiMocks.adminAPI.getStats.mockResolvedValue({
      data: { total_users: 2, active_users: 2, total_scans: 3, cache_entries: 4 },
    })
    apiMocks.adminAPI.getUsers.mockResolvedValue({
      data: {
        users: [
          {
            id: 1,
            username: 'viewer',
            email: 'viewer@example.test',
            role: 'user',
            plan: 'free',
            is_active: true,
            created_at: '2026-07-05T00:00:00',
          },
        ],
      },
    })
    apiMocks.adminAPI.getScans.mockResolvedValue({
      data: {
        scans: [
          {
            id: 8,
            date: '2026-07-05T00:00:00',
            market: 'stocks',
            total_scanned: 10,
            total_matched: 2,
            duration: 0.5,
          },
        ],
      },
    })
    apiMocks.adminAPI.getAuditLogs.mockResolvedValue({
      data: {
        audit_logs: [
          {
            id: 3,
            admin_user_id: 99,
            admin_email: 'admin@example.test',
            action: 'update_user',
            target_type: 'user',
            target_id: 1,
            details: '{"target_email":"viewer@example.test","updates":{"plan":"premium"}}',
            created_at: '2026-07-05T00:00:00',
          },
        ],
      },
    })
    apiMocks.adminAPI.updateUser.mockResolvedValue({ data: {} })
  })

  it('renders admin stats and lets the user table update a plan', async () => {
    const user = userEvent.setup()
    render(<AdminPanel />)

    expect(await screen.findByText('Total Users')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /users/i }))

    expect(await screen.findByText('viewer@example.test')).toBeInTheDocument()
    await user.selectOptions(screen.getByDisplayValue('Free'), 'premium')

    expect(apiMocks.adminAPI.updateUser).toHaveBeenCalledWith(1, { plan: 'premium' })

    await user.click(screen.getByRole('button', { name: /audit log/i }))

    expect(await screen.findByText('update_user')).toBeInTheDocument()
    expect(screen.getByText('viewer@example.test updated: plan')).toBeInTheDocument()
  })
})
