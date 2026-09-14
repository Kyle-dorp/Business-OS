import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach } from "vitest";

// Each test gets a clean DOM and a clean browser. localStorage persisting
// between tests would mean a test that signs in leaves the next one signed in,
// which is the frontend version of the order-dependence the backend suite
// already had twice.
beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  cleanup();
});
