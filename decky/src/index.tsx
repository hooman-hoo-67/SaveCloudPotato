/**
 * SaveCloud in Gaming Mode.
 *
 * The desktop interface exists for setting games up; this exists for the
 * one thing that has to work where the Deck is actually used - knowing
 * whether a save is safe to play from, and fixing it when it is not.
 * Registering games, choosing adapters and picking save folders all stay
 * in Desktop Mode, because none of them belong on a controller.
 */

import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  SteamSpinner,
  showModal,
  staticClasses,
} from "@decky/ui";
import { definePlugin, toaster, useQuickAccessVisible } from "@decky/api";
import { FC, useCallback, useEffect, useState } from "react";
import { FaCloud } from "react-icons/fa";

import {
  CheckRow,
  GameRow,
  Installed,
  Synced,
  checkAll,
  explain,
  games as fetchGames,
  installed as fetchInstalled,
  logs,
  resolve,
  sync,
  syncAll,
} from "./api";
import { Activity } from "./activity";
import { Conflict } from "./conflict";

/** How many log lines to fetch for the activity view. */
const LOG_LINES = 40;

/** What the panel is currently waiting on, if anything. */
type Busy = string | null;

/** The marker `busy` carries while every game is synchronizing. */
const EVERYTHING = "*";

//
// How many times to ask before believing the backend is unreachable,
// and how long to wait between asking. Short enough that a genuinely
// broken plugin still says so promptly.
//

const ATTEMPTS = 4;

const RETRY_PAUSE_MS = 700;

const Content: FC = () => {
  const visible = useQuickAccessVisible();

  const [install, setInstall] = useState<Installed | null>(null);
  const [rows, setRows] = useState<GameRow[]>([]);
  const [states, setStates] = useState<Record<string, CheckRow>>({});
  const [busy, setBusy] = useState<Busy>(null);

  //
  // Set when the bridge to the backend itself fails, as opposed to the
  // backend answering with a failure. Those are different problems and
  // only one of them has anything to do with SaveCloud.
  //
  const [broken, setBroken] = useState<string | null>(null);

  /**
   * Re-read everything the panel shows.
   *
   * The three questions are independent, so they go out together - the
   * backend spawns a process per call and serialising them would show a
   * spinner for three round trips instead of one.
   *
   * The whole thing is guarded because a call can reject rather than
   * answer: a backend that failed to load, or a method that is not
   * there, never reaches the code that decides what to render. Without
   * this the panel sits on its spinner forever, which is the least
   * informative way possible to report that something is wrong - and
   * is exactly what a Deck showed.
   */
  const refresh = useCallback(async (attempts = ATTEMPTS) => {
    try {
      const [where, list, checked] = await Promise.all([
        fetchInstalled(),
        fetchGames(),
        checkAll(),
      ]);

      setBroken(null);

      setInstall(where);

      setRows(list.games ?? []);

      const next: Record<string, CheckRow> = {};

      for (const row of checked.games ?? []) {
        next[row.game_id] = row;
      }

      setStates(next);
    } catch (error) {
      //
      // The bridge to the backend is established when the plugin
      // loads, and the panel can mount before it is ready - so the
      // first call of a session can reject for no reason worse than
      // being early. Giving up on one attempt turns that into a
      // permanent-looking failure, which is what a Deck showed after
      // the read stopped waiting for the panel to become visible.
      //
      if (attempts > 1) {
        await new Promise((wake) => setTimeout(wake, RETRY_PAUSE_MS));

        return refresh(attempts - 1);
      }

      setBroken(
        error instanceof Error ? error.message : String(error ?? "unknown"),
      );
    }
  }, []);

  //
  // On mount, and again whenever the panel is opened. The panel stays
  // mounted for the whole session, so a status read before a game was
  // played would still be on screen after it - saying "Up to date"
  // about a save that has since changed.
  //
  // Deliberately not conditional on `visible`. It used to be, and that
  // made the very first read depend on a hook reporting true at the
  // moment of mounting. On a Deck it did not: the backend loaded, no
  // call was ever made, and the panel sat on its spinner forever with
  // nothing in any log to say why, because nothing had gone wrong -
  // nothing had happened at all.
  //
  // Refreshing when the panel closes as well is the cost, and it is a
  // small one next to a panel that never loads.
  //
  useEffect(() => {
    void refresh();
  }, [visible, refresh]);

  /**
   * Report what a synchronization did, or why it did nothing.
   */
  const report = useCallback((name: string, answer: Synced) => {
    if (answer.ok) {
      const done: Record<string, string> = {
        "up-to-date": "Already up to date",
        upload: "Sent to the cloud",
        download: "Brought down from the cloud",
      };

      toaster.toast({
        title: name,
        body: done[answer.action ?? ""] ?? "Synchronized",
      });

      return;
    }

    toaster.toast({
      title: name,
      body: answer.error ?? "Could not synchronize",
      critical: true,
    });
  }, []);

  /**
   * Synchronize one game, and ask about a conflict if there is one.
   *
   * There is no separate "is this a conflict" call. Synchronizing with
   * no resolution given refuses to overwrite anything and answers with
   * both saves described, so the attempt is how the detail is obtained -
   * and it cannot disagree with reality the way a second, earlier check
   * could.
   */
  const onGame = useCallback(
    async (row: GameRow) => {
      setBusy(row.game_id);

      const answer = await sync(row.game_id);

      setBusy(null);

      if (answer.action === "conflict") {
        showModal(
          <Conflict
            name={row.display_name}
            local={answer.local}
            remote={answer.remote}
            onKeep={async (keep) => {
              setBusy(row.game_id);

              const resolved = await resolve(row.game_id, keep);

              setBusy(null);

              report(row.display_name, resolved);

              await refresh();
            }}
          />,
        );

        return;
      }

      report(row.display_name, answer);

      await refresh();
    },
    [refresh, report],
  );

  /**
   * Synchronize everything, and say how it went in one line.
   *
   * A toast per game would bury the panel under notifications on a
   * library of any size, so only the count of failures is reported;
   * which ones failed is then visible in the list itself.
   */
  const onEverything = useCallback(async () => {
    setBusy(EVERYTHING);

    const answer = await syncAll();

    setBusy(null);

    await refresh();

    const attempted = answer.games?.length ?? 0;

    const failures = answer.failures ?? 0;

    if (!attempted) {
      toaster.toast({
        title: "SaveCloud",
        body: "No games have synchronization enabled",
      });

      return;
    }

    toaster.toast({
      title: "SaveCloud",
      body: failures
        ? `${failures} of ${attempted} could not be synchronized`
        : `Synchronized ${attempted} game${attempted === 1 ? "" : "s"}`,
      critical: failures > 0,
    });
  }, [refresh]);

  /**
   * Show what SaveCloud has been doing.
   */
  const onActivity = useCallback(async () => {
    showModal(<Activity answer={await logs(LOG_LINES)} />);
  }, []);

  //
  // The bridge failed, so nothing below can be trusted to load either.
  // Said plainly, with somewhere to look: this is a problem with the
  // plugin rather than with SaveCloud, and Decky keeps its own log.
  //
  if (broken !== null) {
    return (
      <PanelSection title="SaveCloud">
        <PanelSectionRow>
          <div style={{ fontSize: "0.9em" }}>
            The plugin could not reach its backend.
            <div style={{ marginTop: "8px", opacity: 0.8 }}>{broken}</div>
            <div style={{ marginTop: "8px", opacity: 0.8 }}>
              The newest file in ~/homebrew/logs/SaveCloud/ says what the
              backend did, or that it was never asked.
            </div>
          </div>
        </PanelSectionRow>

        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => void refresh()}>
            Try again
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  if (install === null) {
    return (
      <PanelSection>
        <PanelSectionRow>
          <SteamSpinner background="transparent" />
        </PanelSectionRow>
      </PanelSection>
    );
  }

  //
  // Not installed is a normal thing to be, not an error. The plugin can
  // be found in the store before SaveCloud itself is on the machine, so
  // this says what to do about it rather than what went wrong.
  //
  if (!install.ok) {
    return (
      <PanelSection title="SaveCloud">
        <PanelSectionRow>
          <div style={{ fontSize: "0.9em" }}>{install.error}</div>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  //
  // The activity view is offered even with nothing registered, because
  // that is one of the states it explains: a library the plugin cannot
  // read looks identical to an empty one from here.
  //
  const activity = (
    <PanelSection>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          //
          // Which build was found, not just which version exists. A Deck
          // can easily have an old AppImage in Downloads and a newer one
          // installed, and knowing which one the plugin is driving is
          // the first thing worth checking when something looks wrong.
          //
          description={install.version || install.path}
          onClick={() => void onActivity()}
        >
          Recent activity
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );

  if (!rows.length) {
    return (
      <>
        <PanelSection title="SaveCloud">
          <PanelSectionRow>
            <div style={{ fontSize: "0.9em" }}>
              No games are registered yet. Add them in Desktop Mode, then
              they will appear here.
            </div>
          </PanelSectionRow>
        </PanelSection>

        {activity}
      </>
    );
  }

  return (
    <>
      <PanelSection>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={busy !== null}
            onClick={() => void onEverything()}
          >
            {busy === EVERYTHING ? "Synchronizing…" : "Synchronize everything"}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="Games" spinner={busy !== null}>
        {rows.map((row) => (
          <PanelSectionRow key={row.game_id}>
            <ButtonItem
              layout="below"
              label={row.display_name}
              description={
                busy === row.game_id
                  ? "Working…"
                  : !row.sync_enabled
                    ? //
                      // A disabled button beside a state the user cannot
                      // act on reads as a broken panel. Say why instead.
                      //
                      "Synchronization is off for this game"
                    : explain(states[row.game_id] ?? { game_id: row.game_id })
              }
              disabled={busy !== null || !row.sync_enabled}
              onClick={() => void onGame(row)}
            >
              {states[row.game_id]?.action === "conflict" ? "Resolve" : "Sync"}
            </ButtonItem>
          </PanelSectionRow>
        ))}
      </PanelSection>

      {activity}
    </>
  );
};

export default definePlugin(() => ({
  name: "SaveCloud",
  titleView: <div className={staticClasses.Title}>SaveCloud</div>,
  content: <Content />,
  icon: <FaCloud />,
}));
