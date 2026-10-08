import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PersonalizationMenu } from "@/features/templates/PersonalizationMenu";

describe("PersonalizationMenu", () => {
  it("inserts variable with optional fallback", () => {
    const onInsert = vi.fn();
    render(<PersonalizationMenu onInsert={onInsert} />);

    fireEvent.click(screen.getByRole("button", { name: /Personalize/i }));
    fireEvent.click(screen.getByRole("button", { name: /First Name/i }));

    expect(screen.getByRole("dialog", { name: /Insert variable/i })).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("there"), { target: { value: "there" } });
    fireEvent.click(screen.getByRole("button", { name: /^Insert$/i }));

    expect(onInsert).toHaveBeenCalledWith("{{first_name|there}}");
  });
});
