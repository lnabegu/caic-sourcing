import { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Slider } from '../components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { ThumbsUp, ThumbsDown, FileText, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { pipelineApi, ScoredSource } from '../lib/api';
import { SCORING_PROFILES, calculateScore, ScoringProfile } from '../types';

// Map backend snake_case ScoredSource to the shape the UI expects
function mapSource(s: ScoredSource) {
  return {
    id: s.url,
    url: s.url,
    title: s.title ?? s.url,
    sourceType: s.source_type ?? 'unknown',
    publishDate: '',
    coverageTopics: [] as string[],
    namedOfficials: [] as { name: string; role: string; context: string }[],
    commitments: [] as { actor: string; commitment: string; amount: string | null; timeline: string | null }[],
    unmetNeeds: [] as string[],
    geographicSpecificity: '',
    sourceLanguage: '',
    namedOrganizations: [] as string[],
    eventSpecificity: s.event_specificity / 10,
    actionability: s.actionability / 10,
    accountabilitySignal: s.accountability_signal / 10,
    communityProximity: s.community_proximity / 10,
    independence: s.independence / 10,
    compositeScore: s.composite_score / 10,
  };
}

export default function Results() {
  const navigate = useNavigate();
  const location = useLocation();
  const locationState = location.state as { taskId?: string; event?: Record<string, string> } | null;
  const taskId = locationState?.taskId;
  const event = locationState?.event;

  const [selectedProfile, setSelectedProfile] = useState<string>('default');
  const [customWeights, setCustomWeights] = useState<ScoringProfile>(SCORING_PROFILES.default);
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [expandedSource, setExpandedSource] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<string, 'like' | 'dislike' | null>>({});

  const [sources, setSources] = useState<ReturnType<typeof mapSource>[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState<string>('pending');
  const [pollError, setPollError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!taskId) return;

    const cacheKey = `results:${taskId}`;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      const { sources: cachedSources } = JSON.parse(cached);
      setSources(cachedSources);
      setPipelineStatus('completed');
      return;
    }

    const poll = async () => {
      try {
        const status = await pipelineApi.status(taskId);
        setPipelineStatus(status.status);

        if (status.status === 'completed') {
          clearInterval(intervalRef.current!);
          const results = await pipelineApi.results(taskId);
          const mapped = results.sources.map(mapSource);
          sessionStorage.setItem(cacheKey, JSON.stringify({ sources: mapped }));
          setSources(mapped);
        } else if (status.status === 'failed') {
          clearInterval(intervalRef.current!);
          setPollError(status.error ?? 'Pipeline failed');
        }
      } catch (err) {
        clearInterval(intervalRef.current!);
        setPollError(err instanceof Error ? err.message : 'Failed to fetch status');
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 2000);
    return () => clearInterval(intervalRef.current!);
  }, [taskId]);

  const rankedSources = useMemo(() => {
    const profile = isCustomMode ? customWeights : SCORING_PROFILES[selectedProfile];
    return [...sources]
      .map((source) => ({
        ...source,
        currentScore: calculateScore(
          { ...source, scores: { default: 0, accountability: 0, community: 0, climate: 0, actionable: 0 } },
          profile,
        ),
      }))
      .sort((a, b) => b.currentScore - a.currentScore);
  }, [selectedProfile, customWeights, isCustomMode, sources]);

  const handleProfileChange = (profile: string) => {
    if (profile === 'custom') {
      setIsCustomMode(true);
    } else {
      setIsCustomMode(false);
      setSelectedProfile(profile);
      setCustomWeights(SCORING_PROFILES[profile]);
    }
  };

  const handleWeightChange = (key: keyof ScoringProfile, value: number) => {
    const newVal = value / 100;
    const others = Object.keys(customWeights).filter((k) => k !== key) as (keyof ScoringProfile)[];
    const remaining = 1 - newVal;
    const otherSum = others.reduce((s, k) => s + customWeights[k], 0);
    const normalized = { ...customWeights, [key]: newVal };
    if (otherSum > 0) {
      others.forEach((k) => {
        normalized[k] = (customWeights[k] / otherSum) * remaining;
      });
    } else {
      others.forEach((k) => {
        normalized[k] = remaining / others.length;
      });
    }
    setCustomWeights(normalized);
  };

  const WeightSlider = ({ label, value, onCommit }: { label: string; value: number; onCommit: (v: number) => void }) => {
    const [display, setDisplay] = useState(value * 100);
    // Keep display in sync when other sliders cause this one to change
    useState(() => { setDisplay(value * 100); });
    return (
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm text-[#6b6b68]">{label}</span>
          <span className="text-sm">{Math.round(display)}%</span>
        </div>
        <Slider
          value={[display]}
          onValueChange={([v]) => setDisplay(v)}
          onValueCommit={([v]) => { setDisplay(v); onCommit(v); }}
          max={100}
          step={1}
          className="w-full"
        />
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[#fafaf8]">
      <div className="border-b border-[#e8e6e1] bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <h2 className="text-xl">Search Results</h2>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-8"
        >
          <Card className="p-6 border-[#e8e6e1]">
            <h3 className="mb-4">Scoring Profile</h3>
            <Tabs value={isCustomMode ? 'custom' : selectedProfile} onValueChange={handleProfileChange}>
              <TabsList className="grid grid-cols-5 mb-6 bg-[#f5f4f0]">
                <TabsTrigger value="default">Default</TabsTrigger>
                <TabsTrigger value="accountability">Accountability</TabsTrigger>
                <TabsTrigger value="community">Community</TabsTrigger>
                <TabsTrigger value="climate">Climate</TabsTrigger>
                <TabsTrigger value="actionable">Actionable</TabsTrigger>
              </TabsList>
            </Tabs>

            <Button
              variant={isCustomMode ? 'default' : 'outline'}
              className={`w-full mb-6 ${isCustomMode ? 'bg-[#2c5f5f] hover:bg-[#234949]' : 'border-[#d4d2cc]'}`}
              onClick={() => setIsCustomMode(!isCustomMode)}
            >
              {isCustomMode ? 'Using Custom Weights' : 'Customize Weights'}
            </Button>

            {isCustomMode && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="grid md:grid-cols-2 lg:grid-cols-5 gap-4"
              >
                <WeightSlider
                  label="Event Specificity"
                  value={customWeights.eventSpecificity}
                  onCommit={(v) => handleWeightChange('eventSpecificity', v)}
                />
                <WeightSlider
                  label="Actionability"
                  value={customWeights.actionability}
                  onCommit={(v) => handleWeightChange('actionability', v)}
                />
                <WeightSlider
                  label="Accountability Signal"
                  value={customWeights.accountabilitySignal}
                  onCommit={(v) => handleWeightChange('accountabilitySignal', v)}
                />
                <WeightSlider
                  label="Community Proximity"
                  value={customWeights.communityProximity}
                  onCommit={(v) => handleWeightChange('communityProximity', v)}
                />
                <WeightSlider
                  label="Independence"
                  value={customWeights.independence}
                  onCommit={(v) => handleWeightChange('independence', v)}
                />
              </motion.div>
            )}
            {isCustomMode && (
              <div className="pt-4 text-xs text-[#6b6b68] text-center">
                Total: {Math.round(Object.values(customWeights).reduce((a, b) => a + b, 0) * 100)}%
              </div>
            )}
          </Card>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="space-y-4"
        >
        <div className="mb-6">
          {pipelineStatus !== 'completed' && !pollError && (
            <div className="flex items-center gap-3 text-[#6b6b68] mb-4">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm capitalize">{pipelineStatus}…</span>
            </div>
          )}
          {pollError && (
            <p className="text-sm text-red-500 mb-4">{pollError}</p>
          )}
          <h3 className="mb-2">
            {pipelineStatus === 'completed' ? `Found ${rankedSources.length} Sources` : 'Searching…'}
          </h3>
          <p className="text-sm text-[#6b6b68]">
            Ranked by {isCustomMode ? 'custom weights' : `${selectedProfile} profile`}
          </p>
        </div>

        {rankedSources.map((source, index) => (
              <motion.div
                key={source.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05, duration: 0.4 }}
              >
                <Card className="overflow-hidden border-[#e8e6e1] hover:shadow-md transition-shadow">
                  <div className="p-6">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-[#2c5f5f] text-white text-sm">
                            {index + 1}
                          </span>
                          <Badge variant="outline" className="border-[#8b9d83] text-[#8b9d83]">
                            {source.sourceType}
                          </Badge>
                          <span className="text-xs text-[#6b6b68]">{source.publishDate}</span>
                        </div>
                        <h4 className="mb-2">{source.title}</h4>
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-[#2c5f5f] hover:underline"
                        >
                          {source.url}
                        </a>
                      </div>
                      <div className="text-right ml-4">
                        <div className="text-2xl text-[#2c5f5f] mb-1">
                          {source.currentScore.toFixed(2)}
                        </div>
                        <div className="text-xs text-[#6b6b68]">score</div>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 mb-4">
                      {source.coverageTopics.slice(0, 4).map((topic) => (
                        <Badge key={topic} variant="secondary" className="bg-[#f5f4f0] text-[#1a1a18]">
                          {topic}
                        </Badge>
                      ))}
                    </div>

                    <div className="grid grid-cols-5 gap-3 mb-4 text-center">
                      {[
                        { label: 'Event', value: source.eventSpecificity },
                        { label: 'Action', value: source.actionability },
                        { label: 'Accountability', value: source.accountabilitySignal },
                        { label: 'Community', value: source.communityProximity },
                        { label: 'Independence', value: source.independence },
                      ].map((metric) => (
                        <div key={metric.label}>
                          <div className="text-xs text-[#6b6b68] mb-1">{metric.label}</div>
                          <div className="h-1.5 bg-[#e8e6e1] rounded-full overflow-hidden">
                            <div
                              className="h-full bg-[#8b9d83]"
                              style={{ width: `${metric.value * 100}%` }}
                            />
                          </div>
                          <div className="text-xs mt-1">{(metric.value * 100).toFixed(0)}%</div>
                        </div>
                      ))}
                    </div>

                    <div className="flex items-center justify-between pt-4 border-t border-[#e8e6e1]">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setExpandedSource(expandedSource === source.id ? null : source.id)}
                        className="text-[#2c5f5f] hover:bg-[#2c5f5f]/5"
                      >
                        {expandedSource === source.id ? (
                          <>
                            <ChevronUp className="mr-1 h-4 w-4" />
                            Hide Details
                          </>
                        ) : (
                          <>
                            <ChevronDown className="mr-1 h-4 w-4" />
                            Show Details
                          </>
                        )}
                      </Button>
                      <div className="flex gap-2">
                        <Button
                          variant={feedback[source.id] === 'like' ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => setFeedback({ ...feedback, [source.id]: 'like' })}
                          className={feedback[source.id] === 'like' ? 'bg-[#8b9d83] hover:bg-[#7a8b74]' : 'border-[#d4d2cc]'}
                        >
                          <ThumbsUp className="h-4 w-4" />
                        </Button>
                        <Button
                          variant={feedback[source.id] === 'dislike' ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => setFeedback({ ...feedback, [source.id]: 'dislike' })}
                          className={feedback[source.id] === 'dislike' ? 'bg-[#c44536] hover:bg-[#a83a2c]' : 'border-[#d4d2cc]'}
                        >
                          <ThumbsDown className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    <AnimatePresence>
                      {expandedSource === source.id && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.3 }}
                          className="mt-4 pt-4 border-t border-[#e8e6e1] space-y-4"
                        >
                          {source.namedOfficials.length > 0 && (
                            <div>
                              <h5 className="text-sm mb-2">Named Officials</h5>
                              <div className="space-y-2">
                                {source.namedOfficials.map((official, i) => (
                                  <div key={i} className="text-sm bg-[#f5f4f0] p-3 rounded">
                                    <div className="mb-1">
                                      <strong>{official.name}</strong> — {official.role}
                                    </div>
                                    <div className="text-xs text-[#6b6b68]">{official.context}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {source.commitments.length > 0 && (
                            <div>
                              <h5 className="text-sm mb-2">Commitments</h5>
                              <div className="space-y-2">
                                {source.commitments.map((commitment, i) => (
                                  <div key={i} className="text-sm bg-[#f5f4f0] p-3 rounded">
                                    <div className="mb-1">
                                      <strong>{commitment.actor}</strong>: {commitment.commitment}
                                    </div>
                                    <div className="flex gap-4 text-xs text-[#6b6b68]">
                                      {commitment.amount && <span>Amount: {commitment.amount}</span>}
                                      {commitment.timeline && <span>Timeline: {commitment.timeline}</span>}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {source.unmetNeeds.length > 0 && (
                            <div>
                              <h5 className="text-sm mb-2">Unmet Needs</h5>
                              <ul className="list-disc list-inside space-y-1 text-sm text-[#6b6b68]">
                                {source.unmetNeeds.map((need, i) => (
                                  <li key={i}>{need}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          <div className="grid md:grid-cols-2 gap-4 text-sm">
                            <div>
                              <span className="text-[#6b6b68]">Geographic Specificity:</span>{' '}
                              <strong>{source.geographicSpecificity}</strong>
                            </div>
                            <div>
                              <span className="text-[#6b6b68]">Language:</span>{' '}
                              <strong>{source.sourceLanguage}</strong>
                            </div>
                          </div>

                          {source.namedOrganizations.length > 0 && (
                            <div>
                              <span className="text-sm text-[#6b6b68]">Organizations: </span>
                              <span className="text-sm">{source.namedOrganizations.join(', ')}</span>
                            </div>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </Card>
              </motion.div>
            ))}

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.5 }}
          className="mt-12 text-center"
        >
          <Button
            onClick={() => navigate('/report', { state: { taskId, event, sources: rankedSources } })}
            size="lg"
            className="bg-[#2c5f5f] hover:bg-[#234949] text-white px-8 py-6 h-auto"
          >
            <FileText className="mr-2 h-5 w-5" />
            Generate Comprehensive Report
          </Button>
        </motion.div>
        </motion.div>
      </div>
    </div>
  );
}
