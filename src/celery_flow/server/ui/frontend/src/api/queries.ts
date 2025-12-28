/**
 * TanStack Query hooks for API data fetching.
 *
 * Polling is only enabled when WebSocket is disconnected.
 * When WS is connected, real-time updates come via WS invalidation.
 */

import { useQuery } from '@tanstack/react-query'
import { useWebSocketContext } from '@/hooks/WebSocketContext'
import {
  fetchGraph,
  fetchGraphs,
  fetchHealth,
  fetchTask,
  fetchTaskRegistry,
  fetchTasks,
  type GraphListResponse,
  type GraphResponse,
  type HealthResponse,
  type TaskDetailResponse,
  type TaskListResponse,
  type TaskRegistryResponse,
} from './client'

// Polling interval when WebSocket is disconnected
const POLL_INTERVAL = 5000

export function useTasks(params?: {
  limit?: number
  offset?: number
  state?: string
  name?: string
}) {
  const { isConnected } = useWebSocketContext()

  return useQuery<TaskListResponse>({
    queryKey: ['tasks', params],
    queryFn: () => fetchTasks(params),
    // Only poll when WS is disconnected
    refetchInterval: isConnected ? false : POLL_INTERVAL,
  })
}

export function useTask(taskId: string) {
  const { isConnected } = useWebSocketContext()

  return useQuery<TaskDetailResponse>({
    queryKey: ['tasks', taskId],
    queryFn: () => fetchTask(taskId),
    enabled: !!taskId,
    // Only poll when WS is disconnected
    refetchInterval: isConnected ? false : POLL_INTERVAL,
  })
}

export function useGraphs(limit?: number) {
  const { isConnected } = useWebSocketContext()

  return useQuery<GraphListResponse>({
    queryKey: ['graphs', limit],
    queryFn: () => fetchGraphs(limit),
    // Only poll when WS is disconnected
    refetchInterval: isConnected ? false : POLL_INTERVAL,
  })
}

export function useGraph(rootId: string) {
  const { isConnected } = useWebSocketContext()

  return useQuery<GraphResponse>({
    queryKey: ['graphs', rootId],
    queryFn: () => fetchGraph(rootId),
    enabled: !!rootId,
    // Only poll when WS is disconnected
    refetchInterval: isConnected ? false : POLL_INTERVAL,
  })
}

export function useHealth() {
  const { isConnected } = useWebSocketContext()

  return useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: fetchHealth,
    // Sync with data polling interval so status changes are consistent
    refetchInterval: isConnected ? false : POLL_INTERVAL,
  })
}

export function useTaskRegistry(query?: string) {
  const { isConnected } = useWebSocketContext()

  return useQuery<TaskRegistryResponse>({
    queryKey: ['taskRegistry', query],
    queryFn: () => fetchTaskRegistry(query),
    // Registry refreshes less frequently
    refetchInterval: isConnected ? false : 30000,
  })
}
