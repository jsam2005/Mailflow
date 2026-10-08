import axios from "axios";

import type { ApiErrorBody } from "@/types/auth";

export function getErrorMessage(error: unknown, fallback = "Something went wrong"): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiErrorBody | undefined;
    return data?.message || data?.error || error.message || fallback;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}
