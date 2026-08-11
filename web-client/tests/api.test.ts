import { describe, expect, it } from "vitest";
import { ApiError } from "../src/api";

describe("API error contract", () => {
  it("keeps the safe server error code and message", () => {
    const error = new ApiError({ error: { code: "PROJECT_BUSY", message: "Another operation is running.", details: { operation_id: "x" } } });
    expect(error.code).toBe("PROJECT_BUSY");
    expect(error.message).toContain("Another operation");
  });
});
