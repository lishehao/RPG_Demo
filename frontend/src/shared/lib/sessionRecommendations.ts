import type { SessionUiMove } from '@/shared/api/types';

export type RecommendedMove = SessionUiMove & {
  sourceIndex: number;
};

function isGlobalMove(moveId: string) {
  return moveId.startsWith('global.');
}

export function deriveRecommendedMoves(moves: SessionUiMove[], limit = 3): RecommendedMove[] {
  const indexed = moves.map((move, sourceIndex) => ({ ...move, sourceIndex }));
  const nonGlobal = indexed.filter((move) => !isGlobalMove(move.move_id));
  const globalMoves = indexed.filter((move) => isGlobalMove(move.move_id));
  const orderedGlobals = [
    ...globalMoves.filter((move) => move.move_id !== 'global.help_me_progress'),
    ...globalMoves.filter((move) => move.move_id === 'global.help_me_progress'),
  ];

  return [...nonGlobal, ...orderedGlobals].slice(0, limit);
}
