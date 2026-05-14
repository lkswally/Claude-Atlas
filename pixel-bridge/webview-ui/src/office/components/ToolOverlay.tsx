import { useState, useEffect } from 'react'
import type { ToolActivity } from '../types.js'
import type { OfficeState } from '../engine/officeState.js'
import type { SubagentCharacter } from '../../hooks/useExtensionMessages.js'
import { TILE_SIZE, CharacterState } from '../types.js'
import { TOOL_OVERLAY_VERTICAL_OFFSET, CHARACTER_SITTING_OFFSET_PX } from '../../constants.js'

interface ToolOverlayProps {
  officeState: OfficeState
  agents: number[]
  agentTools: Record<number, ToolActivity[]>
  subagentCharacters: SubagentCharacter[]
  containerRef: React.RefObject<HTMLDivElement | null>
  zoom: number
  panRef: React.RefObject<{ x: number; y: number }>
  onCloseAgent: (id: number) => void
}

/** Derive a short human-readable activity string from tools/status */
function getActivityText(
  agentId: number,
  agentTools: Record<number, ToolActivity[]>,
  isActive: boolean,
): string {
  const tools = agentTools[agentId]
  if (tools && tools.length > 0) {
    // Find the latest non-done tool
    const activeTool = [...tools].reverse().find((t) => !t.done)
    if (activeTool) {
      if (activeTool.permissionWait) return 'Needs approval'
      return activeTool.status
    }
    // All tools done but agent still active (mid-turn) — keep showing last tool status
    if (isActive) {
      const lastTool = tools[tools.length - 1]
      if (lastTool) return lastTool.status
    }
  }

  return 'Idle'
}

export function ToolOverlay({
  officeState,
  agents,
  agentTools,
  subagentCharacters,
  containerRef,
  zoom,
  panRef,
  onCloseAgent,
}: ToolOverlayProps) {
  const [, setTick] = useState(0)
  useEffect(() => {
    let rafId = 0
    let intervalId = 0

    const rafTick = () => {
      setTick((n) => n + 1)
      rafId = requestAnimationFrame(rafTick)
    }
    const intervalTick = () => setTick((n) => n + 1)

    const startRaf = () => {
      if (intervalId) { clearInterval(intervalId); intervalId = 0 }
      rafId = requestAnimationFrame(rafTick)
    }
    const startInterval = () => {
      if (rafId) { cancelAnimationFrame(rafId); rafId = 0 }
      intervalId = window.setInterval(intervalTick, 200) // ~5fps when hidden — labels don't need to move fast
    }

    const onVisibilityChange = () => {
      if (document.hidden) startInterval(); else startRaf()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    if (document.hidden) startInterval(); else startRaf()

    return () => {
      cancelAnimationFrame(rafId)
      clearInterval(intervalId)
      document.removeEventListener('visibilitychange', onVisibilityChange)
    }
  }, [])

  const el = containerRef.current
  if (!el) return null
  const rect = el.getBoundingClientRect()
  const dpr = window.devicePixelRatio || 1
  const canvasW = Math.round(rect.width * dpr)
  const canvasH = Math.round(rect.height * dpr)
  const layout = officeState.getLayout()
  const mapW = layout.cols * TILE_SIZE * zoom
  const mapH = layout.rows * TILE_SIZE * zoom
  const deviceOffsetX = Math.floor((canvasW - mapW) / 2) + Math.round(panRef.current.x)
  const deviceOffsetY = Math.floor((canvasH - mapH) / 2) + Math.round(panRef.current.y)

  const selectedId = officeState.selectedAgentId
  const hoveredId = officeState.hoveredAgentId

  // All character IDs
  const allIds = [...agents, ...subagentCharacters.map((s) => s.id)]

  return (
    <>
      {allIds.map((id) => {
        const ch = officeState.characters.get(id)
        if (!ch) return null

        const isSelected = selectedId === id
        const isHovered = hoveredId === id
        const isSub = ch.isSubagent
        const showDetails = isSelected || isHovered

        // Position above character
        const sittingOffset = ch.state === CharacterState.TYPE ? CHARACTER_SITTING_OFFSET_PX : 0
        const screenX = (deviceOffsetX + ch.x * zoom) / dpr
        const screenY = (deviceOffsetY + (ch.y + sittingOffset - TOOL_OVERLAY_VERTICAL_OFFSET) * zoom) / dpr

        // When the agent is chatting, the speech bubble occupies the space above the
        // character head. Move the name tag below the sprite to avoid covering the bubble.
        const isChatting = ch.bubbleType === 'chat'
        const spritePx = Math.round(TOOL_OVERLAY_VERTICAL_OFFSET * zoom / dpr)
        const labelTop = isChatting ? screenY + spritePx + 4 : screenY - 24

        // Always show name label; show activity details on hover/select
        const displayName = ch.folderName || (isSub ? 'Subtask' : `Agent #${id}`)

        // Get activity text (only needed when showing details)
        let activityText = ''
        let dotColor: string | null = null
        if (showDetails) {
          const subHasPermission = isSub && ch.bubbleType === 'permission'
          if (isSub) {
            if (subHasPermission) {
              activityText = 'Needs approval'
            } else {
              const sub = subagentCharacters.find((s) => s.id === id)
              activityText = sub ? sub.label : 'Subtask'
            }
          } else {
            activityText = getActivityText(id, agentTools, ch.isActive)
          }

          const tools = agentTools[id]
          const hasPermission = subHasPermission || tools?.some((t) => t.permissionWait && !t.done)
          const hasActiveTools = tools?.some((t) => !t.done)
          const isActive = ch.isActive

          if (hasPermission) {
            dotColor = 'var(--pixel-status-permission)'
          } else if (isActive && hasActiveTools) {
            dotColor = 'var(--pixel-status-active)'
          }
        }

        return (
          <div
            key={id}
            style={{
              position: 'absolute',
              left: screenX,
              top: labelTop,
              transform: 'translateX(-50%)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              pointerEvents: isSelected ? 'auto' : 'none',
              zIndex: isSelected ? 'var(--pixel-overlay-selected-z)' : 'var(--pixel-overlay-z)',
            }}
          >
            {showDetails ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 5,
                  background: 'var(--pixel-bg)',
                  border: isSelected
                    ? '2px solid var(--pixel-border-light)'
                    : '2px solid var(--pixel-border)',
                  borderRadius: 0,
                  padding: isSelected ? '3px 6px 3px 8px' : '3px 8px',
                  boxShadow: 'var(--pixel-shadow)',
                  whiteSpace: 'nowrap',
                  maxWidth: 220,
                }}
              >
                {dotColor && (
                  <span
                    className={ch.isActive && dotColor !== 'var(--pixel-status-permission)' ? 'pixel-agents-pulse' : undefined}
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: dotColor,
                      flexShrink: 0,
                    }}
                  />
                )}
                <div style={{ overflow: 'hidden' }}>
                  <span
                    style={{
                      fontSize: isSub ? '20px' : '22px',
                      fontStyle: isSub ? 'italic' : undefined,
                      color: 'var(--vscode-foreground)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      display: 'block',
                    }}
                  >
                    {activityText}
                  </span>
                  <span
                    style={{
                      fontSize: '16px',
                      color: 'var(--pixel-text-dim)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      display: 'block',
                    }}
                  >
                    {displayName}
                  </span>
                </div>
                {isSelected && !isSub && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      onCloseAgent(id)
                    }}
                    title="Close agent"
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--pixel-close-text)',
                      cursor: 'pointer',
                      padding: '0 2px',
                      fontSize: '26px',
                      lineHeight: 1,
                      marginLeft: 2,
                      flexShrink: 0,
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.color = 'var(--pixel-close-hover)'
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.color = 'var(--pixel-close-text)'
                    }}
                  >
                    ×
                  </button>
                )}
              </div>
            ) : (
              <div
                style={ch.isActive ? {
                  background: 'var(--pixel-green)',
                  border: '1px solid #2a7a50',
                  padding: '2px 7px',
                  boxShadow: '0 0 8px rgba(90,200,140,0.6), var(--pixel-shadow)',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                } : {
                  background: 'var(--pixel-bg)',
                  border: '1px solid var(--pixel-border)',
                  padding: '1px 5px',
                  boxShadow: 'var(--pixel-shadow)',
                  whiteSpace: 'nowrap',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                {ch.isActive && (
                  <span
                    className="pixel-agents-pulse"
                    style={{
                      width: 5,
                      height: 5,
                      borderRadius: '50%',
                      background: '#0a2e1a',
                      flexShrink: 0,
                      display: 'inline-block',
                    }}
                  />
                )}
                <span
                  style={{
                    fontSize: '16px',
                    fontWeight: ch.isActive ? 'bold' : undefined,
                    color: ch.isActive ? '#0a2e1a' : 'var(--pixel-text-dim)',
                  }}
                >
                  {displayName}
                </span>
              </div>
            )}
          </div>
        )
      })}
    </>
  )
}
