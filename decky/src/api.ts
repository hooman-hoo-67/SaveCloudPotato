/**
 * The typed bridge to the Python backend.
 *
 * Nothing here draws anything, and nothing in the widgets calls the
 * backend directly - the same split the desktop interface uses between
 * its facade and its window. It exists so that a change to what the
 * `savecloud` command emits lands in one file.
 *
 * Every call resolves. The backend answers a failure with a document
 * rather than raising, so widgets branch on `ok` instead of catching.
 */

import { callable } from "@decky/api";

/** What every backend route returns at minimum. */
export interface Answer {
  ok: boolean;
  error?: string;
}

export interface Installed extends Answer {
  path?: string;
  version?: string;
}

/** One game, as `savecloud --json list` describes it. */
export interface GameRow {
  game_id: string;
  display_name: string;
  platform: string;
  adapter: string;
  sync_enabled: boolean;
  auto_sync: boolean;
  status: string;
  pending_upload: boolean;
}

export interface Games extends Answer {
  games?: GameRow[];
}

/**
 * What synchronizing one game would do.
 *
 * A game the check could not reach reports `error` instead of `action` -
 * one unpaired game must not blank out the list.
 */
export interface CheckRow {
  game_id: string;
  action?: SyncAction;
  error?: string;
}

export interface Checked extends Answer {
  games?: CheckRow[];
}

export type SyncAction = "up-to-date" | "upload" | "download" | "conflict";

/** One side of a conflict, described well enough to choose it. */
export interface SaveSummary {
  where: string;
  modified: string;
  age: string;
  version: number;
  checksum: string;
}

export interface Synced extends Answer {
  game_id?: string;
  action?: SyncAction;
  applied?: boolean;
  /** Present only when the answer is a conflict. */
  local?: SaveSummary | null;
  remote?: SaveSummary | null;
  reason?: string;
}

export interface SyncedAll extends Answer {
  applied?: boolean;
  failures?: number;
  games?: { game_id: string; action?: SyncAction; error?: string }[];
}

export interface Logs extends Answer {
  path?: string;
  lines?: string[];
}

export const installed = callable<[], Installed>("installed");

export const games = callable<[], Games>("games");

export const checkAll = callable<[], Checked>("check_all");

export const sync = callable<[game_id: string], Synced>("sync");

export const syncAll = callable<[], SyncedAll>("sync_all");

export const resolve = callable<[game_id: string, keep: string], Synced>(
  "resolve",
);

export const logs = callable<[lines: number], Logs>("logs");

/**
 * One line naming a save and when it was written.
 *
 * The same sentence the command line prints, assembled here rather than
 * sent over the wire: the parts are what the backend has, and a caller
 * that wants them laid out differently still can.
 */
export function describe(summary: SaveSummary): string {
  const parts = [summary.where];

  if (summary.age) {
    parts.push(`saved ${summary.age}`);
  }

  if (summary.version) {
    parts.push(`version ${summary.version}`);
  }

  return parts.join(" · ");
}

/**
 * What a game's state means, in words a person can act on.
 *
 * "upload" and "download" are the service's vocabulary, describing
 * which direction bytes move. Nobody thinks about their saves that way,
 * so this says which copy is ahead instead.
 */
export function explain(row: CheckRow): string {
  if (row.error) {
    return row.error;
  }

  switch (row.action) {
    case "up-to-date":
      return "Up to date";

    case "upload":
      return "This device is ahead";

    case "download":
      return "The cloud is ahead";

    case "conflict":
      return "Both changed - needs a decision";

    default:
      return "Not checked yet";
  }
}
