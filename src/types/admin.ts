export interface AdminStats {
  totalUsers: number;
  totalPredictions: number;
  activeUsers: number;
  /** Share of predictions in the last 30 days labelled high-risk (%). */
  highRiskShare: number;
}

export interface UserListItem {
  id: string;
  email: string;
  created_at: string;
  last_sign_in: string | null;
  role: string;
  is_banned: boolean;
}

export interface PredictionStats {
  date: string;
  count: number;
  accuracy: number;
}
