export type Warning = { code: string; message: string };

export type Project = {
  id: string;
  title: string;
  surname_hangul: string;
  surname_hanja: string | null;
  sex: "m" | "f" | "n";
  preferences: Record<string, unknown>;
  constraints: Record<string, unknown>;
  analysis_options: Record<string, unknown>;
  created_at: string;
};

export type Category = {
  score: number | null;
  basis: string;
  label: string;
  nature: string;
  weight: number;
  effective_weight: number;
  disputed?: string[];
};

export type RankedItem = {
  id?: string;
  given_hangul: string;
  given_hanja: string | null;
  full_hangul: string;
  source?: string;
  status?: string;
  overall: number | null;
  gate: { official_hanja: "pass" | "unknown" | "fail"; caution: "review" | "none" };
  categories: Record<string, Category>;
  incomplete: string[];
  confidence: {
    data_verification: string;
    reproducible: boolean;
    school_agreement: { agree_count: number; total: number; note: string };
    ai_subjective: boolean;
  };
  ai_reason: string | null;
  reaction?: "like" | "dislike" | "hold" | null;
};

export const CATEGORY_ORDER = ["phonetic", "meaning", "saju", "numerology", "usability", "preference"] as const;
export const CATEGORY_SHORT: Record<string, string> = {
  phonetic: "발음",
  meaning: "의미",
  saju: "사주",
  numerology: "수리",
  usability: "사용성",
  preference: "선호",
};
