/**
 * Charts.
 *
 * The rules being enforced here are not stylistic. A chart that encodes
 * meaning in colour alone is unreadable to about one man in twelve; a chart
 * with no way to read the underlying numbers is a picture of data rather than
 * data. So: a legend whenever more than one series is drawn, values direct-
 * labelled in text, and a table view on every one of them.
 *
 * The palette itself was checked with the validator rather than by eye — see
 * the header of Charts.jsx for what passed and the one check knowingly
 * relaxed.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { CashChart, LaborChart, RankedBars } from "../components/Charts.jsx";

const series = [
  { date: "2026-09-01", in: 40_000, out: 12_000 },
  { date: "2026-09-02", in: 0, out: 30_000 },
  { date: "2026-09-03", in: 65_000, out: 5_000 },
];

describe("cash in and out", () => {
  it("draws both directions", () => {
    const { container } = render(<CashChart series={series} />);

    expect(container.querySelector(".chart-line.is-in")).toBeInTheDocument();
    expect(container.querySelector(".chart-line.is-out")).toBeInTheDocument();
  });

  it("names both series in a legend, so identity is never colour alone", () => {
    render(<CashChart series={series} />);

    const legend = document.querySelector(".chart-legend");
    expect(within(legend).getByText("In")).toBeInTheDocument();
    expect(within(legend).getByText("Out")).toBeInTheDocument();
  });

  it("omits a direction with no movement rather than drawing a flat line", () => {
    // A row of zeros renders along the axis and reads as a stray rule.
    const { container } = render(
      <CashChart series={series.map((d) => ({ ...d, out: 0 }))} />);

    expect(container.querySelector(".chart-line.is-in")).toBeInTheDocument();
    expect(container.querySelector(".chart-line.is-out")).not.toBeInTheDocument();
  });

  it("the numbers behind it can be read as a table", async () => {
    render(<CashChart series={series} />);

    await userEvent.click(screen.getByRole("button", { name: "Show numbers" }));

    const table = screen.getByRole("table");
    expect(within(table).getByText("2026-09-01")).toBeInTheDocument();
    expect(within(table).getByText("$400")).toBeInTheDocument();
    expect(within(table).getByText("$120")).toBeInTheDocument();
  });

  it("the table hides again", async () => {
    render(<CashChart series={series} />);

    await userEvent.click(screen.getByRole("button", { name: "Show numbers" }));
    await userEvent.click(screen.getByRole("button", { name: "Hide numbers" }));

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("describes itself to a screen reader", () => {
    render(<CashChart series={series} />);

    expect(screen.getByRole("img", { name: /Cash in and out per day/ })).toBeInTheDocument();
  });

  it("renders nothing rather than an empty frame when there is no data", () => {
    const { container } = render(<CashChart series={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("labor against forecast", () => {
  const days = [
    { date: "2026-09-14", percent: 28 },
    { date: "2026-09-15", percent: 36 },
    { date: "2026-09-16", percent: 47 },
  ];

  it("draws the two lines a manager steers between", () => {
    render(<LaborChart days={days} />);

    expect(screen.getByText("33% target")).toBeInTheDocument();
    expect(screen.getByText("40% ceiling")).toBeInTheDocument();
  });

  it("marks a day that is over the ceiling", () => {
    const { container } = render(<LaborChart days={days} />);

    expect(container.querySelectorAll(".chart-bar.is-over")).toHaveLength(1);
    expect(container.querySelectorAll(".chart-bar.is-tight")).toHaveLength(1);
  });

  it("says what it is dividing by, rather than implying a daily forecast", () => {
    // The forecast is a week total. Pretending otherwise would be inventing a
    // number the product does not have.
    render(<LaborChart days={days} />);

    expect(screen.getByText(/even split of the week's forecast/)).toBeInTheDocument();
  });

  it("skips a day it cannot price rather than drawing it as zero", () => {
    const { container } = render(
      <LaborChart days={[...days, { date: "2026-09-17", percent: null }]} />);

    expect(container.querySelectorAll(".chart-bar")).toHaveLength(3);
  });

  it("shows an unpriced day as a dash in the table", async () => {
    render(<LaborChart days={[{ date: "2026-09-17", percent: null }]} />);

    await userEvent.click(screen.getByRole("button", { name: "Show numbers" }));
    expect(within(screen.getByRole("table")).getByText("—")).toBeInTheDocument();
  });
});

describe("ranked bars", () => {
  const items = [
    { label: "Negroni", value: 52 },
    { label: "G&T", value: 31 },
    { label: "Espresso", value: 18 },
  ];

  it("labels every value in text, not just in bar length", () => {
    render(<RankedBars title="Food cost" items={items} limit={35} />);

    expect(screen.getByText("52%")).toBeInTheDocument();
    expect(screen.getByText("31%")).toBeInTheDocument();
    expect(screen.getByText("18%")).toBeInTheDocument();
  });

  it("marks what is over the line", () => {
    const { container } = render(
      <RankedBars title="Food cost" items={items} limit={35} limitLabel="35% target" />);

    expect(container.querySelectorAll(".chart-bars-row.is-over")).toHaveLength(1);
    expect(screen.getByText("35% target")).toBeInTheDocument();
  });

  it("draws the limit where the limit is", () => {
    const { container } = render(<RankedBars title="Food cost" items={items} limit={35} />);
    expect(container.querySelector(".chart-bars-limit")).toBeInTheDocument();
  });

  it("works with no limit at all", () => {
    const { container } = render(<RankedBars title="Stock" items={items} unit=" days" />);

    expect(container.querySelector(".chart-bars-limit")).not.toBeInTheDocument();
    expect(screen.getByText("52 days")).toBeInTheDocument();
  });

  it("has a table too", async () => {
    render(<RankedBars title="Food cost" items={items} />);

    await userEvent.click(screen.getByRole("button", { name: "Show numbers" }));
    expect(within(screen.getByRole("table")).getByText("Negroni")).toBeInTheDocument();
  });
});
