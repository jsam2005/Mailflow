const ERROR_LABELS: Record<string, string> = {
  AUTH_EXPIRED: "Authentication expired",
  RATE_LIMITED: "Provider rate limit reached",
  QUOTA_EXCEEDED: "Sending quota exceeded",
  TEMPORARY_PROVIDER_ERROR: "Provider temporarily unavailable",
  INVALID_RECIPIENT: "Invalid recipient",
  RECIPIENT_NO_LONGER_ELIGIBLE: "Recipient no longer eligible",
  UNCERTAIN_PROVIDER_RESULT: "Send result could not be confirmed",
  TEST_RECIPIENT_NOT_ALLOWED: "Not on test allowlist",
  CAMPAIGN_CANCELLED: "Campaign cancelled",
};

export function formatMessageError(code: string | null | undefined, fallback?: string | null): string {
  if (code && ERROR_LABELS[code]) {
    return ERROR_LABELS[code];
  }
  if (fallback && fallback.length < 120) {
    return fallback;
  }
  return code || fallback || "Send failed";
}
