import { render, screen, waitFor } from "@testing-library/react";
import { CoverageFailureCard } from "@/components/chat/CoverageFailureCard";
import { CoverageView } from "@/components/records/CoverageView";
import { applyEvent, newAnswer } from "@/lib/chat/state";
import { FAKE_COVERAGE } from "@/lib/fake/data";
import { FAILURES } from "@/lib/copy";

const done = (reason: "out_of_scope" | "not_found", message_key: string | null) =>
  applyEvent(newAnswer("q"), {
    event: "done",
    data: { message_id: null, from_cache: false, refused: true, reason, message_key },
  });

describe("a refusal picks its own screen", () => {
  it("a source the dataset does not hold is 'not in our dataset', not an out-of-coverage screen", () => {
    expect(done("out_of_scope", "out_of_scope:not_in_dataset").failure).toBe("notInDataset");
  });
  it("other out-of-scope refusals keep the coverage screen; no match stays 'not found'", () => {
    expect(done("out_of_scope", "out_of_scope:needs_lower_court").failure).toBe("outsideCoverage");
    expect(done("out_of_scope", null).failure).toBe("outsideCoverage");
    expect(done("not_found", "not_found").failure).toBe("notFound");
  });
});

describe("the coverage sentence comes from the API, not from the web app", () => {
  it("shows the API's sentence for the out-of-coverage screen", async () => {
    render(<CoverageFailureCard kind="outsideCoverage" />);
    await waitFor(() => expect(screen.getByText(FAKE_COVERAGE.sentence)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "What the dataset covers" })).toHaveAttribute("href", "/coverage");
  });
  it("shows the API's 'not in our dataset' message", async () => {
    render(<CoverageFailureCard kind="notInDataset" />);
    await waitFor(() => expect(screen.getByText(FAKE_COVERAGE.not_in_dataset_message)).toBeInTheDocument());
  });
  it("the built-in fallback names no category", () => {
    for (const k of ["outsideCoverage", "notInDataset"] as const) {
      expect(FAILURES[k].body).not.toMatch(/court|act|tribunal|central|state/i);
    }
  });
});

describe("coverage page", () => {
  it("lists exactly what the API lists, flags a placeholder, and carries date, credit and notice", () => {
    const { container } = render(<CoverageView coverage={FAKE_COVERAGE} />);
    expect(screen.getByText(/has not been measured yet/)).toBeInTheDocument();
    for (const i of [...FAKE_COVERAGE.courts, ...FAKE_COVERAGE.instruments]) {
      expect(screen.getByText(i.label)).toBeInTheDocument();
    }
    expect(screen.getByText("Sample exclusions")).toBeInTheDocument();
    expect(screen.getByText(/Data as of 2026-08-31/)).toBeInTheDocument();
    expect(screen.getByText(/CC BY 4.0/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/state acts|regulations/i);
  });
  it("shows the service-down card when the call failed", () => {
    render(<CoverageView coverage={null} />);
    expect(screen.getByRole("alert")).toHaveTextContent(FAILURES.serviceError.title);
  });
  it("a 'measured' file is not labelled a placeholder", () => {
    render(<CoverageView coverage={{ ...FAKE_COVERAGE, status: "measured" }} />);
    expect(screen.queryByText(/has not been measured yet/)).toBeNull();
  });
});
