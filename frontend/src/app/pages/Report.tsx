import { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Separator } from '../components/ui/separator';
import { ArrowLeft, Download, Share2, Loader2, MessageCircle, X, Send } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { pipelineApi } from '../lib/api';

interface ChatMsg { role: 'user' | 'assistant'; content: string; }

function ChatPanel({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState('');
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || thinking) return;
    const next: ChatMsg[] = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    setThinking(true);
    try {
      const { reply } = await pipelineApi.chat(taskId, text, messages);
      setMessages([...next, { role: 'assistant', content: reply }]);
    } catch {
      setMessages([...next, { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' }]);
    } finally {
      setThinking(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      transition={{ duration: 0.2 }}
      className="fixed bottom-24 right-6 w-96 h-[520px] bg-white rounded-2xl shadow-2xl border border-[#e8e6e1] flex flex-col z-50"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#e8e6e1]">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-[#2c5f5f]" />
          <span className="text-sm font-medium">Ask about this report</span>
        </div>
        <button onClick={onClose} className="text-[#6b6b68] hover:text-[#1a1a18]">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-sm text-[#6b6b68] mt-8 space-y-2">
            <p>Ask anything about this event.</p>
            <div className="space-y-1 mt-4">
              {['Who led the response?', 'What funding was committed?', 'What are the main gaps?'].map(q => (
                <button key={q} onClick={() => { setInput(q); }}
                  className="block w-full text-left text-xs px-3 py-2 rounded-lg bg-[#f5f4f0] hover:bg-[#e8e6e1] text-[#6b6b68]">
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] px-3 py-2 rounded-xl text-sm leading-relaxed ${
              m.role === 'user'
                ? 'bg-[#2c5f5f] text-white'
                : 'bg-[#f5f4f0] text-[#1a1a18]'
            }`}>
              {m.content}
            </div>
          </div>
        ))}
        {thinking && (
          <div className="flex justify-start">
            <div className="bg-[#f5f4f0] px-3 py-2 rounded-xl">
              <Loader2 className="h-4 w-4 animate-spin text-[#6b6b68]" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="p-3 border-t border-[#e8e6e1] flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Ask a question…"
          className="flex-1 text-sm px-3 py-2 rounded-lg border border-[#e8e6e1] bg-[#fafaf8] outline-none focus:border-[#2c5f5f]"
        />
        <button
          onClick={send}
          disabled={!input.trim() || thinking}
          className="p-2 rounded-lg bg-[#2c5f5f] text-white disabled:opacity-40 hover:bg-[#234949]"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </motion.div>
  );
}

interface EventData {
  location?: string;
  eventType?: string;
  eventDate?: string;
  description?: string;
}

// Parse plain-text report into named sections
function parseSections(text: string): { title: string; body: string }[] {
  const lines = text.split('\n');
  const sections: { title: string; body: string }[] = [];
  let current: { title: string; lines: string[] } | null = null;

  for (const line of lines) {
    // Match: optional ##/**, optional number+dot, then the heading text, optional colon/**
    const heading = line.match(/^(?:#{1,3}\s*|\*{1,2})?(\d+\.\s+[A-Za-z][A-Za-z0-9\s,&'/()-]+?)(?::|\*{1,2})?$/);
    if (heading && heading[1].trim().length > 3) {
      if (current) sections.push({ title: current.title, body: current.lines.join('\n').trim() });
      current = { title: heading[1].replace(/^\d+\.\s+/, '').trim(), lines: [] };
    } else if (current) {
      current.lines.push(line);
    }
  }
  if (current) sections.push({ title: current.title, body: current.lines.join('\n').trim() });
  return sections;
}

const Section = ({ title, body }: { title: string; body: string }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5 }}
    className="mb-8"
  >
    <h2 className="mb-4 pb-2 border-b-2 border-[#2c5f5f]">{title}</h2>
    <div className="space-y-3">
      {body.split('\n').filter(l => l.trim()).map((para, i) => (
        <p key={i} className="text-[#6b6b68] leading-relaxed text-sm">{para}</p>
      ))}
    </div>
  </motion.div>
);

export default function Report() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as { taskId?: string; event?: EventData; sources?: unknown[] } | null;

  const taskId = state?.taskId ?? sessionStorage.getItem('lastTaskId') ?? undefined;
  const event: EventData = state?.event ?? {};
  const sourceCount = state?.sources?.length ?? 0;

  useEffect(() => {
    if (state?.taskId) sessionStorage.setItem('lastTaskId', state.taskId);
  }, [state?.taskId]);

  const [reportText, setReportText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  const handleShare = async () => {
    const url = `${window.location.origin}/report?task=${taskId}`;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePrint = () => window.print();

  useEffect(() => {
    if (!taskId) return;
    const cacheKey = `report:${taskId}`;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) { setReportText(cached); return; }
    setLoading(true);
    pipelineApi.generateReport(taskId)
      .then(r => { sessionStorage.setItem(cacheKey, r.report_text); setReportText(r.report_text); })
      .catch(e => setError(e instanceof Error ? e.message : 'Failed to generate report'))
      .finally(() => setLoading(false));
  }, [taskId]);

  const sections = reportText ? parseSections(reportText) : [];
  const eventTitle = [event.eventType, event.location].filter(Boolean).join(' — ') || 'Climate Event';
  const eventDate = event.eventDate
    ? new Date(event.eventDate).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
    : null;

  return (
    <div className="min-h-screen bg-[#fafaf8]">
      <div className="border-b border-[#e8e6e1] bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex justify-between items-center">
          <Button
            onClick={() => navigate('/results', { state })}
            variant="ghost"
            className="text-[#2c5f5f] hover:bg-[#2c5f5f]/5"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Results
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" className="border-[#d4d2cc]" onClick={handleShare} disabled={!taskId}>
              <Share2 className="mr-2 h-4 w-4" />
              {copied ? 'Copied!' : 'Share'}
            </Button>
            <Button className="bg-[#2c5f5f] hover:bg-[#234949]" disabled={!reportText} onClick={handlePrint}>
              <Download className="mr-2 h-4 w-4" />
              Export PDF
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-12 text-center"
        >
          <div className="inline-block mb-4 px-4 py-1.5 bg-[#2c5f5f]/10 rounded-full">
            <span className="text-sm text-[#2c5f5f]">Comprehensive Analysis Report</span>
          </div>
          <h1 className="mb-3 text-[2.5rem] leading-tight">{eventTitle}</h1>
          <p className="text-[#6b6b68]">
            {sourceCount} sources analyzed{eventDate ? ` · ${eventDate}` : ''}
            {event.location ? ` · ${event.location}` : ''}
          </p>
        </motion.div>

        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-[#2c5f5f]" />
            <p className="text-[#6b6b68]">Generating report from {sourceCount} sources…</p>
            <p className="text-xs text-[#6b6b68]">This usually takes a minute or two. </p>
          </div>
        )}

        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600 text-center">
            {error}
          </div>
        )}

        {!loading && sections.length > 0 && (
          <Card className="p-8 mb-8 border-[#e8e6e1]">
            {sections.map((section, i) => (
              <div key={section.title}>
                <Section title={section.title} body={section.body} />
                {i < sections.length - 1 && <Separator className="my-8 bg-[#e8e6e1]" />}
              </div>
            ))}

            <div className="mt-8 p-6 bg-[#f5f4f0] rounded-lg text-center">
              <p className="text-xs text-[#6b6b68]">
                Generated by the CAIC Source Discovery Pipeline · {sourceCount} sources · {eventDate ?? ''}
              </p>
            </div>
          </Card>
        )}
      </div>

      {taskId && (
        <>
          <button
            onClick={() => setChatOpen(o => !o)}
            className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-[#2c5f5f] text-white shadow-lg flex items-center justify-center z-50 hover:bg-[#234949] transition-colors"
          >
            <MessageCircle className="h-6 w-6" />
          </button>
          <AnimatePresence>
            {chatOpen && <ChatPanel taskId={taskId} onClose={() => setChatOpen(false)} />}
          </AnimatePresence>
        </>
      )}
    </div>
  );
}
