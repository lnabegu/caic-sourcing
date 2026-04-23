import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import { Info, Search } from 'lucide-react';
import { motion } from 'motion/react';
import { pipelineApi } from '../lib/api';

export default function Home() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    location: '',
    eventType: '',
    eventDate: '',
    description: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { task_id } = await pipelineApi.run({
        location: formData.location,
        event_type: formData.eventType,
        event_date: formData.eventDate,
        description: formData.description,
      });
      navigate('/results', { state: { taskId: task_id, event: formData } });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Something went wrong';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#fafaf8] via-[#f5f4f0] to-[#e8e6e1]">
      <div className="max-w-4xl mx-auto px-6 py-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="text-center mb-12">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2, duration: 0.5 }}
              className="inline-block mb-4 px-4 py-1.5 bg-[#2c5f5f]/10 rounded-full"
            >
              <span className="text-sm text-[#2c5f5f]">Climate Action Information for Communities</span>
            </motion.div>
            <h1 className="mb-4 text-[2.75rem] leading-tight">
              News Finder for
              <br />
              Climate Response
            </h1>
            <p className="text-[#6b6b68] max-w-2xl mx-auto leading-relaxed">
              Search and analyze sources related to specific climate events. Our pipeline extracts metadata,
              identifies decision-makers, tracks commitments, and surfaces accountability signals.
            </p>

            <div className="mt-4 flex justify-center">
              <Dialog>
                <DialogTrigger asChild>
                  <button className="inline-flex items-center gap-1.5 text-xs text-[#2c5f5f]/70 hover:text-[#2c5f5f] transition-colors">
                    <Info className="h-3.5 w-3.5" />
                    How to authenticate
                  </button>
                </DialogTrigger>
                <DialogContent className="max-w-lg">
                  <DialogHeader>
                    <DialogTitle>Generating an access token</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 text-sm text-[#3a3a38]">
                    <p>
                      The API requires a JWT bearer token. Use the interactive docs at{' '}
                      <a
                        href="https://caic-sourcing.onrender.com/docs"
                        target="_blank"
                        rel="noreferrer"
                        className="text-[#2c5f5f] underline underline-offset-2"
                      >
                        caic-sourcing.onrender.com/docs
                      </a>{' '}
                      to register and get one.
                    </p>
                    <ol className="list-decimal list-inside space-y-2 text-[#4a4a47]">
                      <li>
                        Open the docs and expand <strong>POST /api/auth/jwt/register</strong>.
                      </li>
                      <li>
                        Click <em>Try it out</em>, fill in your email, password, and name, then
                        click <em>Execute</em>.
                      </li>
                      <li>
                        Copy the <code className="bg-[#f0efeb] px-1 py-0.5 rounded text-xs">access_token</code> from the response body.
                      </li>
                      <li>
                        Open your browser console on this page and run:
                        <pre className="mt-1.5 bg-[#f0efeb] rounded p-3 text-xs overflow-x-auto whitespace-pre-wrap break-all">
{`localStorage.setItem('caic_access_token', 'PASTE_TOKEN_HERE')`}
                        </pre>
                      </li>
                      <li>Reload the page — you're authenticated.</li>
                    </ol>
                    <p className="text-[#6b6b68] text-xs">
                      Already registered? Use <strong>POST /api/auth/jwt/login</strong> instead and
                      copy the token the same way.
                    </p>
                  </div>
                </DialogContent>
              </Dialog>
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.6 }}
            className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-xl shadow-[#2c5f5f]/5 p-8 border border-[#e8e6e1]"
          >
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid md:grid-cols-2 gap-6">
                <div className="space-y-2">
                  <Label htmlFor="location">Location</Label>
                  <Input
                    id="location"
                    placeholder="e.g., Mozambique, Beira"
                    value={formData.location}
                    onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    required
                    className="bg-[#fafaf8] border-[#d4d2cc]"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="eventType">Event Type</Label>
                  <Input
                    id="eventType"
                    placeholder="e.g., Cyclone, Flood, Drought"
                    value={formData.eventType}
                    onChange={(e) => setFormData({ ...formData, eventType: e.target.value })}
                    required
                    className="bg-[#fafaf8] border-[#d4d2cc]"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="eventDate">Event Date</Label>
                <Input
                  id="eventDate"
                  type="date"
                  value={formData.eventDate}
                  onChange={(e) => setFormData({ ...formData, eventDate: e.target.value })}
                  required
                  className="bg-[#fafaf8] border-[#d4d2cc]"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Additional Context (Optional)</Label>
                <Textarea
                  id="description"
                  placeholder="Provide any additional details about the event or your search focus..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={4}
                  className="bg-[#fafaf8] border-[#d4d2cc] resize-none"
                />
              </div>

              {error && (
                <p className="text-sm text-red-500">{error}</p>
              )}
              <Button
                type="submit"
                disabled={loading}
                className="w-full bg-[#2c5f5f] hover:bg-[#234949] text-white h-12 group disabled:opacity-60"
              >
                <Search className="mr-2 h-5 w-5 transition-transform group-hover:scale-110" />
                {loading ? 'Starting pipeline…' : 'Search & Analyze Sources'}
              </Button>
            </form>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6, duration: 0.6 }}
            className="mt-12 grid md:grid-cols-3 gap-6"
          >
            {[
              { title: 'Extract Metadata', desc: 'Identify officials, organizations, and commitments' },
              { title: 'Score Sources', desc: 'Rank by event specificity, actionability, and independence' },
              { title: 'Generate Reports', desc: 'Create comprehensive accountability assessments' },
            ].map((feature, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.7 + i * 0.1, duration: 0.5 }}
                className="text-center p-6 rounded-xl bg-white/50 border border-[#e8e6e1]"
              >
                <h3 className="mb-2">{feature.title}</h3>
                <p className="text-sm text-[#6b6b68]">{feature.desc}</p>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </div>
    </div>
  );
}
