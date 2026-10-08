import { render, screen } from "@testing-library/react";
import { Users } from "lucide-react";
import { describe, expect, it } from "vitest";

import { StatCard } from "@/components/StatCard";

describe("StatCard", () => {
  it("renders label and value", () => {
    render(<StatCard label="Contacts" value="2,430" icon={Users} />);
    expect(screen.getByText("Contacts")).toBeInTheDocument();
    expect(screen.getByText("2,430")).toBeInTheDocument();
  });
});
