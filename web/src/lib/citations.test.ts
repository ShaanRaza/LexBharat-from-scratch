import { describe, expect, it } from "vitest";
import { citationHref, citationState, segmentAnswer } from "./citations";
import type { Citation } from "./types";

describe("citationState (when is a tick allowed?)", () => {
  it("tick only for status exactly 'verified'", () => {
    expect(citationState({ status: "verified" })).toBe("verified");
  });

  it("warning mark for 'partly'", () => {
    expect(citationState({ status: "partly" })).toBe("partial");
  });

  it("never a tick for 'unverified'", () => {
    expect(citationState({ status: "unverified" })).toBe("unverified");
  });

  it("never a tick for a missing, odd or merely truthy status", () => {
    const odd = (status: unknown) => ({ status }) as unknown as Pick<Citation, "status">;
    expect(citationState(odd(undefined))).toBe("unverified");
    expect(citationState(odd(true))).toBe("unverified");
    expect(citationState(odd("Verified"))).toBe("unverified");
    expect(citationState(odd("yes"))).toBe("unverified");
  });
});

describe("segmentAnswer (nothing citation-shaped before the citations event)", () => {
  it("hides [S1] markers while citations have not arrived", () => {
    const segs = segmentAnswer("Bail is the rule [S1] and jail the exception.", null);
    expect(segs.every((s) => s.type === "text")).toBe(true);
    expect(segs.map((s) => (s.type === "text" ? s.text : "")).join("")).not.toContain("[S1]");
  });

  it("hides a half-arrived marker at the end of streaming text", () => {
    const joined = (t: string) =>
      segmentAnswer(t, null).map((s) => (s.type === "text" ? s.text : "")).join("");
    expect(joined("Bail is the rule [S")).toBe("Bail is the rule ");
    expect(joined("Bail is the rule [S1")).toBe("Bail is the rule ");
  });

  it("turns known markers into chips once citations are known", () => {
    const segs = segmentAnswer("A [S1] B [S2].", new Set(["S1", "S2"]));
    expect(segs.filter((s) => s.type === "cite")).toHaveLength(2);
  });

  it("drops a marker whose source was removed by the verifier", () => {
    const segs = segmentAnswer("A [S1] B [S2].", new Set(["S1"]));
    expect(segs.filter((s) => s.type === "cite")).toEqual([{ type: "cite", sourceId: "S1" }]);
  });
});

describe("citationHref", () => {
  const base: Citation = {
    source_id: "S1", record_id: "r 1", title: "t", citation_string: null, url: null,
    status: "verified", status_label: null, kind: "judgment", anchor: "p5",
    act_slug: null, section: null, act_status: null,
  };
  it("links a judgment to its paragraph anchor", () => {
    expect(citationHref(base)).toBe("/cases/r%201#p5");
  });
  it("links an Act citation to its section page", () => {
    expect(citationHref({ ...base, kind: "act", act_slug: "x", section: "3" })).toBe("/acts/x/3");
  });
  it("gives no in-site link when the kind is unknown (never a wrong link)", () => {
    expect(citationHref({ ...base, kind: null })).toBeNull();
  });
});
