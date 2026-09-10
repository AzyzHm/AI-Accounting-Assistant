export type Role = 'USER' | 'ADMIN' | 'SUPER_ADMIN';

export interface UserProfile {
  uid: string;
  email: string | null;
  display_name: string | null;
  role: Role;
  approved: boolean;
}

export interface UpdateProfileRequest {
  display_name?: string;
  email?: string;
}
