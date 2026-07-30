/**
 * Recent log entries, on the device that cannot read a log file.
 *
 * When a synchronization fails during a session there is nowhere in
 * Gaming Mode for it to say why - the toast is gone, and the log lives
 * in a directory no controller can reach. Rebooting into Desktop Mode to
 * read a file is not a diagnosis anyone should have to perform, so the
 * last few lines are shown here.
 */

import { ConfirmModal } from "@decky/ui";
import { FC } from "react";

import { Logs } from "./api";

export interface ActivityProps {
  answer: Logs;
  /** Supplied by `showModal`, not by the caller. */
  closeModal?: () => void;
}

export const Activity: FC<ActivityProps> = ({ answer, closeModal }) => {
  const lines = answer.lines ?? [];

  const body = !answer.ok ? (
    <div>{answer.error ?? "The log could not be read."}</div>
  ) : !lines.length ? (
    <div>Nothing has been logged yet.</div>
  ) : (
    //
    // Newest first. The interesting line is almost always the last thing
    // that happened, and scrolling to the bottom of a log with a
    // thumbstick is worse than reading it upwards.
    //
    <div
      style={{
        maxHeight: "50vh",
        overflowY: "scroll",
        fontSize: "0.8em",
        fontFamily: "monospace",
        whiteSpace: "pre-wrap",
      }}
    >
      {[...lines].reverse().map((line, index) => (
        <div key={index} style={{ marginBottom: "4px" }}>
          {line}
        </div>
      ))}
    </div>
  );

  return (
    <ConfirmModal
      bAlertDialog
      strTitle="Recent activity"
      strDescription={body}
      strOKButtonText="Close"
      closeModal={closeModal}
    />
  );
};
