/**
 * Choosing between two saves, in Gaming Mode.
 *
 * A conflict is the one thing here that cannot be resolved for the
 * user - both copies contain real progress and only they know which
 * matters. So this dialog's whole job is to describe the two saves well
 * enough that the choice is obvious, and then get out of the way.
 */

import { ConfirmModal } from "@decky/ui";
import { FC, ReactNode } from "react";

import { SaveSummary, describe } from "./api";

export interface ConflictProps {
  name: string;
  local?: SaveSummary | null;
  remote?: SaveSummary | null;
  onKeep: (keep: "local" | "remote") => void;
  /** Supplied by `showModal`, not by the caller. */
  closeModal?: () => void;
}

/**
 * What to call the cloud side.
 *
 * The remote save names the device that wrote it when it knows, which
 * is far more use than "remote". When it does not - an older upload, or
 * one made before devices were named - it says so generically, and
 * repeating that verbatim on a button reads as a bug.
 */
function remoteLabel(remote?: SaveSummary | null): string {
  const where = remote?.where;

  if (!where || where === "Another device") {
    return "Keep the cloud copy";
  }

  return `Keep ${where}`;
}

/**
 * One side of the choice, labelled.
 */
const Side: FC<{ heading: string; summary?: SaveSummary | null }> = ({
  heading,
  summary,
}) => {
  if (!summary) {
    return null;
  }

  return (
    <div style={{ marginTop: "8px" }}>
      <div style={{ fontWeight: "bold" }}>{heading}</div>
      <div style={{ opacity: 0.8 }}>{describe(summary)}</div>
    </div>
  );
};

export const Conflict: FC<ConflictProps> = ({
  name,
  local,
  remote,
  onKeep,
  closeModal,
}) => {
  const description: ReactNode = (
    <div>
      <div>
        {name} was played on two devices since the last synchronization.
        Choose which save to continue from.
      </div>

      <Side heading="This device" summary={local} />
      <Side heading="The cloud" summary={remote} />

      <div style={{ marginTop: "12px", opacity: 0.8 }}>
        Whichever save loses is kept in this game's version history, so
        neither one is lost.
      </div>
    </div>
  );

  return (
    <ConfirmModal
      strTitle={`Conflicting saves`}
      strDescription={description}
      strOKButtonText="Keep this device"
      strMiddleButtonText={remoteLabel(remote)}
      strCancelButtonText="Decide later"
      onOK={() => onKeep("local")}
      onMiddleButton={() => onKeep("remote")}
      closeModal={closeModal}
    />
  );
};
