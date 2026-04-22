export interface EventInput {
  location: string;
  eventType: string;
  eventDate: string;
  description?: string;
}

export interface NamedOfficial {
  name: string;
  role: string;
  context: string;
}

export interface Commitment {
  actor: string;
  commitment: string;
  amount: string | null;
  timeline: string | null;
}

export type GeographicSpecificity = 'global' | 'regional' | 'national' | 'district' | 'sub_district';
export type CoverageTopic = 'overview' | 'causes' | 'response' | 'commitments' | 'gaps' | 'accountability' | 'preparedness' | 'recovery';

export interface SourceMetadata {
  id: string;
  title: string;
  url: string;
  sourceType: string;
  publishDate: string;
  namedOfficials: NamedOfficial[];
  namedOrganizations: string[];
  commitments: Commitment[];
  unmetNeeds: string[];
  geographicSpecificity: GeographicSpecificity;
  sourceLanguage: string;
  citedSources: string[];
  eventSpecificity: number;
  actionability: number;
  accountabilitySignal: number;
  communityProximity: number;
  independence: number;
  coverageTopics: CoverageTopic[];
  scores: {
    default: number;
    accountability: number;
    community: number;
    climate: number;
    actionable: number;
  };
}

export interface ScoringProfile {
  eventSpecificity: number;
  actionability: number;
  accountabilitySignal: number;
  communityProximity: number;
  independence: number;
}

export const SCORING_PROFILES: Record<string, ScoringProfile> = {
  default: {
    eventSpecificity: 0.25,
    actionability: 0.25,
    accountabilitySignal: 0.20,
    communityProximity: 0.15,
    independence: 0.15,
  },
  accountability: {
    eventSpecificity: 0.15,
    actionability: 0.15,
    accountabilitySignal: 0.35,
    communityProximity: 0.10,
    independence: 0.25,
  },
  community: {
    eventSpecificity: 0.20,
    actionability: 0.30,
    communityProximity: 0.30,
    accountabilitySignal: 0.10,
    independence: 0.10,
  },
  climate: {
    eventSpecificity: 0.30,
    actionability: 0.10,
    accountabilitySignal: 0.15,
    communityProximity: 0.10,
    independence: 0.35,
  },
  actionable: {
    eventSpecificity: 0.20,
    actionability: 0.40,
    accountabilitySignal: 0.15,
    communityProximity: 0.15,
    independence: 0.10,
  },
};

export function calculateScore(source: SourceMetadata, profile: ScoringProfile): number {
  return (
    source.eventSpecificity * profile.eventSpecificity +
    source.actionability * profile.actionability +
    source.accountabilitySignal * profile.accountabilitySignal +
    source.communityProximity * profile.communityProximity +
    source.independence * profile.independence
  );
}
