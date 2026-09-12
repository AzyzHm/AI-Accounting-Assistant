import { Role } from './user.model';

export interface LoginEvent {
  id: string;
  uid: string;
  email: string | null;
  display_name: string | null;
  role: Role;
  ip: string | null;
  user_agent: string | null;
  created_at: string | number | null;
}

export interface UsageTotal {
  uid: string;
  email: string | null;
  display_name: string | null;
  role: Role;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  message_count: number;
  search_credits_used?: number;
  updated_at?: string | number | null;
}

export interface UsageLimits {
  daily_token_limit: number;
  daily_search_limit: number;
  monthly_token_limit: number;
  monthly_search_limit: number;
}

export interface UsagePeriodCounts {
  daily_tokens: number;
  daily_searches: number;
  monthly_tokens: number;
  monthly_searches: number;
}

export interface UserLimitsDetail {
  limits: UsageLimits;
  usage: UsagePeriodCounts;
  daily_reset_at: string;
  monthly_reset_at: string;
}
