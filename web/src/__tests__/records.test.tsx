import { render, screen } from "@testing-library/react";
import { ActSection } from "@/components/records/ActSection";
import { Judgment } from "@/components/records/Judgment";
import { FAKE_CASE, FAKE_SECTIONS } from "@/lib/fake/data";

describe("ActSection", () => {
  it("says in-force status not checked when act_status is unfilled", () => {
    render(<ActSection s={FAKE_SECTIONS[0]} />);
    expect(screen.getByText("In-force status not checked for this Act.")).toBeInTheDocument();
    expect(screen.queryByText("In force")).toBeNull();
  });
  it("shows In force only when checked", () => {
    render(<ActSection s={FAKE_SECTIONS[1]} />);
    expect(screen.getByText("In force")).toBeInTheDocument();
  });
  it("carries date, credit and notice", () => {
    render(<ActSection s={FAKE_SECTIONS[0]} />);
    expect(screen.getByText(/Data as of 2026-08-31/)).toBeInTheDocument();
    expect(screen.getByText("Data: Open India Law by Vaquill AI, CC BY 4.0")).toBeInTheDocument();
  });
});

describe("Judgment", () => {
  it("renders paragraph anchors and the citation as recorded", () => {
    const { container } = render(<Judgment c={FAKE_CASE} />);
    expect(container.querySelector("#p12")).not.toBeNull();
    expect(screen.getByText(/as recorded in the dataset/)).toBeInTheDocument();
    expect(screen.getByText(/CC BY 4.0/)).toBeInTheDocument();
  });
});

describe("no party names", () => {
  it("judgment page does not show the case title", () => {
    render(<Judgment c={FAKE_CASE} />);
    expect(screen.queryByText(/Sample v\. Sample/)).toBeNull();
  });
});

import { judgmentHeading } from "@/components/records/Judgment";
describe("judgment heading and titles", () => {
  it("falls back to court and year", () => {
    expect(judgmentHeading({ ...FAKE_CASE, citation_string: null, case_number: null })).toBe("Supreme Court of India, 2020");
  });
  it("never renders the title in chat citations", async () => {
    const { ChatScreen } = await import("@/components/chat/ChatScreen");
    const { fireEvent, waitFor } = await import("@testing-library/react");
    render(<ChatScreen />);
    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "x" } });
    fireEvent.click(screen.getByText("Ask"));
    await waitFor(() => expect(screen.getAllByText(/Record found/).length).toBeGreaterThan(0));
    expect(screen.queryByText(/Sample v\. Sample/)).toBeNull();
  });
});
