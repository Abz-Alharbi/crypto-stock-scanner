import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import WatchlistPage from './WatchlistPage'
import useAuthStore from '../../store/useAuthStore'
import useMarketStore from '../../store/useMarketStore'

describe('WatchlistRow', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: { id: 1, username: 'aziz', email: 'aziz@example.test' },
      token: 'token',
      isAuthenticated: true,
      showAuthModal: false,
      authMode: 'login',
    })
  })

  it('renders a watchlist row and wires view/remove actions', async () => {
    const user = userEvent.setup()
    const loadWatchlist = vi.fn()
    const openDetail = vi.fn()
    const removeFromWatchlist = vi.fn()
    const updateWatchlistNotes = vi.fn().mockResolvedValue()

    useMarketStore.setState({
      watchlist: [
        {
          id: 11,
          provider_symbol: 'X:BTCUSD',
          display_symbol: 'X:BTCUSD',
          market: 'crypto',
          notes: 'Breakout watch',
        },
      ],
      isLoadingWatchlist: false,
      loadWatchlist,
      openDetail,
      removeFromWatchlist,
      updateWatchlistNotes,
    })

    render(<WatchlistPage />)

    expect(loadWatchlist).toHaveBeenCalled()
    expect(screen.getByText('X:BTCUSD')).toBeInTheDocument()
    expect(screen.getByText('crypto')).toBeInTheDocument()
    expect(screen.getByText('Breakout watch')).toBeInTheDocument()

    await user.click(screen.getByTitle('View details'))
    await user.click(screen.getByTitle('Edit notes'))
    await user.clear(screen.getByRole('textbox'))
    await user.type(screen.getByRole('textbox'), 'Updated note')
    await user.click(screen.getByTitle('Save notes'))
    await user.click(screen.getByTitle('Remove from watchlist'))

    expect(openDetail).toHaveBeenCalledWith('X:BTCUSD')
    expect(updateWatchlistNotes).toHaveBeenCalledWith(11, 'Updated note')
    expect(removeFromWatchlist).toHaveBeenCalledWith(11)
  })
})
