// Shared types for Pulse Mini App frontend.

export type MiniAppUser = {
  userId: number | null;
  username: string | null;
  displayName: string;
  balance: number;
  isAdmin: boolean;
  isOwner: boolean;
  isLinked: boolean;
  isLeft: boolean;
};

export type MiniAppSection = {
  id: string;
  title: string;
  description: string;
  state: 'ready' | 'next';
};

export type BootstrapResponse = {
  ok: boolean;
  environment: string;
  launchMode: 'telegram' | 'browser';
  user: MiniAppUser;
  sections: MiniAppSection[];
};

export type ProfileStats = {
  totalMessages: number;
  totalChars: number;
  reactionsGiven: number;
  lastActiveDate: string | null;
};

export type ProfileData = {
  userId: number;
  username: string | null;
  displayName: string;
  firstName: string | null;
  lastName: string | null;
  balance: number;
  frozenBalance: number;
  isAdmin: boolean;
  isOwner: boolean;
  isQualified: boolean;
  isLeft: boolean;
  joinedAt: string | null;
  lastActive: string | null;
  referralCode: string | null;
  referralCount: number;
  stats: ProfileStats;
  hasBbsProfile: boolean;
};

export type ProfileResponse = {
  ok: boolean;
  profile?: ProfileData;
  error?: string;
};
