import React, { useState, useEffect } from 'react';
import './App.css';

interface Draft {
  channel: string;
  subject?: string;
  body: string;
  score?: number;
  approved: boolean;
}

interface StageInfo {
  status: 'pending' | 'running' | 'completed' | 'failed';
  message: string;
}

interface Campaign {
  campaign_id: string;
  status: string;
  current_stage: string;
  target_company?: string;
  target_role?: string;
  drafts: Draft[];
  error?: string;
  stages?: Record<string, StageInfo>;
}

const STAGE_NAMES = [
  { key: 'ingestion', label: 'Data Ingestion', icon: '📥' },
  { key: 'persona', label: 'Persona Analysis', icon: '🎯' },
  { key: 'drafting', label: 'Draft Generation', icon: '✍️' },
  { key: 'scoring', label: 'Quality Scoring', icon: '⭐' },
  { key: 'approval', label: 'Human Review', icon: '👤' },
  { key: 'execution', label: 'Message Sending', icon: '🚀' },
  { key: 'persistence', label: 'Data Storage', icon: '💾' },
];

function App() {
  const [urlInput, setUrlInput] = useState('');
  const [textInput, setTextInput] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [loading, setLoading] = useState(false);
  const [approvalChoices, setApprovalChoices] = useState<Record<string, 'approve' | 'regen' | 'skip'>>({});
  const [pollingInterval, setPollingInterval] = useState<NodeJS.Timeout | null>(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [pollingInterval]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleStartCampaign = async () => {
    setLoading(true);
    
    // Simulate demo campaign with mock data
    setTimeout(() => {
      const mockCampaign: Campaign = {
        campaign_id: 'demo-' + Date.now(),
        status: 'running',
        current_stage: 'approval',
        target_company: 'TechCorp Inc',
        target_role: 'Senior Software Engineer',
        drafts: [
          {
            channel: 'email',
            subject: 'Exciting opportunity at our growing startup',
            body: 'Hi there!\n\nI noticed your impressive background in software engineering at TechCorp Inc. We\'re building something revolutionary in the AI space and would love to chat about how your expertise could help shape our product.\n\nWould you be open to a quick 15-minute call this week?\n\nBest regards,\nSarah',
            score: 8.5,
            approved: false
          },
          {
            channel: 'linkedin',
            subject: '',
            body: 'Hey! Loved your recent post about microservices architecture. We\'re tackling similar challenges at scale and I think you\'d find our approach interesting. Would you be open to connecting?',
            score: 7.8,
            approved: false
          },
          {
            channel: 'whatsapp',
            subject: '',
            body: 'Hi! 👋 Quick intro - I\'m Sarah from AI Innovations. Saw your profile and think you\'d be amazing for what we\'re building. Free for a quick call this week?',
            score: 7.5,
            approved: false
          },
          {
            channel: 'sms',
            subject: '',
            body: 'Hi! Quick intro - I\'m Sarah from AI Innovations. Saw your profile and think you\'d be a great fit for what we\'re building. Coffee chat this week?',
            score: 6.9,
            approved: false
          },
          {
            channel: 'instagram',
            subject: '',
            body: 'Hey! 👋 Love your content on tech and innovation. We\'re building something cool in AI and would love to get your thoughts. DM me if interested!',
            score: 7.2,
            approved: false
          }
        ],
        stages: {
          ingestion: { status: 'completed', message: 'Successfully extracted profile data' },
          persona: { status: 'completed', message: 'Identified key interests and background' },
          drafting: { status: 'completed', message: 'Generated 5 channel-specific messages' },
          scoring: { status: 'completed', message: 'Evaluated message quality and relevance' },
          approval: { status: 'running', message: 'Waiting for human review' },
          execution: { status: 'pending', message: 'Ready to send approved messages' },
          persistence: { status: 'pending', message: 'Will save campaign data' }
        }
      };
      
      setCampaign(mockCampaign);
      setLoading(false);
    }, 1500);
  };

  const pollCampaignStatus = async (campaignId: string) => {
    // Clear existing interval if any
    if (pollingInterval) {
      clearInterval(pollingInterval);
    }

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`/api/v1/campaigns/${campaignId}`);
        const data = await response.json();
        setCampaign(data);
        
        // Stop polling if completed or failed
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval);
          setPollingInterval(null);
        }
      } catch (error) {
        console.error('Failed to fetch campaign status:', error);
      }
    }, 2000);

    setPollingInterval(interval);
  };

  const handleDraftAction = (channel: string, action: 'approve' | 'regen' | 'skip') => {
    setApprovalChoices(prev => ({ ...prev, [channel]: action }));
  };

  const handleSubmitApprovals = async () => {
    if (!campaign) return;
    const approved = Object.entries(approvalChoices)
      .filter(([_, action]) => action === 'approve')
      .map(([channel]) => channel);

    const regen = Object.entries(approvalChoices)
      .filter(([_, action]) => action === 'regen')
      .map(([channel]) => channel);

    const skipped = Object.entries(approvalChoices)
      .filter(([_, action]) => action === 'skip')
      .map(([channel]) => channel);

    // Apply choices locally immediately so the UI reflects changes (demo/offline friendly)
    const updatedDrafts = campaign.drafts.map(d => {
      // Approve: mark approved
      if (approved.includes(d.channel)) {
        return { ...d, approved: true };
      }

      // Regenerate: produce a new variation for the body and update score
      if (regen.includes(d.channel)) {
        const timestamp = new Date().toLocaleTimeString();
        const newBody = `Regenerated (${timestamp}):\n\n${d.body.split('\n').slice(0, 2).join('\n')}\n\nWanted to follow up with a fresher outreach tone — would you be open to a brief call?\n\nBest,\nSarah`;
        const newScore = Math.max(5 + Math.random() * 4, 5).toFixed(1);
        return { ...d, body: newBody, score: parseFloat(newScore), approved: false };
      }

      // Skip: mark as not approved and append a small badge in the body
      if (skipped.includes(d.channel)) {
        const newBody = `${d.body}\n\n[SKIPPED] This draft was skipped by the reviewer.`;
        return { ...d, body: newBody, approved: false };
      }

      return d;
    });

    setCampaign(prev => prev ? { ...prev, drafts: updatedDrafts } : prev);
    // Clear choices after applying locally
    setApprovalChoices({});

    // Try to notify backend if available (non-blocking)
    try {
      await fetch(`/api/v1/campaigns/${campaign.campaign_id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved, regen, skipped }),
      });

      // If backend supports polling, start it
      pollCampaignStatus(campaign.campaign_id);
    } catch (error) {
      // Backend might be unavailable in demo mode — that's fine; UI already updated
      console.warn('Backend approve call failed (demo mode?):', error);
    }
  };

  const handleCompleteCampaign = () => {
    if (!campaign) return;

    // Mark remaining stages as completed
    const finalStages: Record<string, StageInfo> = {
      ingestion: { status: 'completed', message: 'Profile data extracted' },
      persona: { status: 'completed', message: 'Persona analysis complete' },
      drafting: { status: 'completed', message: 'Messages generated' },
      scoring: { status: 'completed', message: 'Quality scores assigned' },
      approval: { status: 'completed', message: 'Review finished' },
      execution: { status: 'completed', message: 'Approved messages sent' },
      persistence: { status: 'completed', message: 'Campaign data saved' },
    };

    setCampaign(prev =>
      prev
        ? { ...prev, status: 'completed', current_stage: 'persistence', stages: finalStages }
        : prev
    );
  };

  const getStageStatus = (stageKey: string): StageInfo => {
    if (!campaign || !campaign.stages) {
      return { status: 'pending', message: 'Waiting...' };
    }
    return campaign.stages[stageKey] || { status: 'pending', message: 'Waiting...' };
  };

  // Ensure all draft cards have identical heights for consistent UX
  useEffect(() => {
    if (!campaign || !campaign.drafts) return;

    const equalize = () => {
      const cards = Array.from(document.querySelectorAll('.draft-card')) as HTMLElement[];
      if (!cards.length) return;
      // reset heights to measure natural sizes
      cards.forEach(c => c.style.height = 'auto');
      const max = Math.max(...cards.map(c => c.offsetHeight));
      cards.forEach(c => c.style.height = `${max}px`);
    };

    // run after a small delay to allow DOM to settle
    const t = setTimeout(equalize, 50);
    window.addEventListener('resize', equalize);

    // observe DOM changes to re-equalize if drafts update
    const grid = document.querySelector('.drafts-grid');
    const obs = new MutationObserver(() => setTimeout(equalize, 50));
    if (grid) obs.observe(grid, { childList: true, subtree: true });

    return () => {
      clearTimeout(t);
      window.removeEventListener('resize', equalize);
      obs.disconnect();
    };
  }, [campaign]);

  return (
    <div className="App">
      <div className="header">
        <h1>🚀 Outreach Engine</h1>
        <p>AI-Powered Hyper-Personalized Cold Outreach</p>
      </div>

      <div className="content">
        {!campaign && (
          <div className="input-section">
            <h2>Provide Target Information</h2>
            <p className="section-subtitle">Choose any input method below or combine multiple sources for better personalization</p>
            
            <div className="input-grid">
              <div className="input-card">
                <div className="input-card-header">
                  <div className="input-icon">🔗</div>
                  <h3>LinkedIn Profile</h3>
                </div>
                <div className="input-group">
                  <input
                    type="text"
                    placeholder="https://linkedin.com/in/example"
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    className="modern-input"
                  />
                </div>
              </div>

              <div className="input-card">
                <div className="input-card-header">
                  <div className="input-icon">📝</div>
                  <h3>Text Information</h3>
                </div>
                <div className="input-group">
                  <textarea
                    placeholder="Paste bio, profile details, or any relevant information..."
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                    className="modern-input"
                  />
                </div>
              </div>

              <div className="input-card">
                <div className="input-card-header">
                  <div className="input-icon">📄</div>
                  <h3>Upload Document</h3>
                </div>
                <div className="input-group">
                  <div className={`file-upload-modern ${file ? 'has-file' : ''}`}>
                    <input
                      type="file"
                      accept=".pdf,.doc,.docx"
                      onChange={handleFileChange}
                      id="file-input"
                    />
                    <label htmlFor="file-input">
                      {file ? (
                        <>
                          <div className="file-icon">📄</div>
                          <div className="file-name">{file.name}</div>
                          <div className="file-action">Click to change</div>
                        </>
                      ) : (
                        <>
                          <div className="file-icon-placeholder">📤</div>
                          <div className="file-prompt">Click or drop PDF/DOC</div>
                        </>
                      )}
                    </label>
                  </div>
                </div>
              </div>
            </div>

            <button
              className="btn-primary"
              onClick={handleStartCampaign}
              disabled={loading || (!urlInput.trim() && !textInput.trim() && !file)}
            >
              {loading ? 'Launching Campaign...' : 'Launch Campaign'}
            </button>
          </div>
        )}

        {campaign && (
          <>
            <div className="campaign-header">
              <h2>Campaign In Progress</h2>
              {campaign.target_company && (
                <div className="target-badge">
                  <span className="label">🎯 Target:</span>
                  <span className="value">{campaign.target_role || 'Professional'} at {campaign.target_company}</span>
                </div>
              )}
            </div>

            <div className="progress-section">
              <div className="progress-section-title">Workflow Pipeline</div>
              <div className="stages">
                {STAGE_NAMES.map(({ key, label, icon }) => {
                  const stageInfo = getStageStatus(key);
                  return (
                    <div key={key} className={`stage ${stageInfo.status}`}>
                      <div className="stage-icon">{icon}</div>
                      <div className="stage-info">
                        <div className="stage-name">{label}</div>
                        <div className="stage-message">
                          {stageInfo.message || `${stageInfo.status}...`}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {campaign.drafts && campaign.drafts.length > 0 && (
              <div className="drafts-section">
                <div className="progress-section-title">Generated Messages</div>
                <div className="drafts-grid">
                  {campaign.drafts.map((draft: Draft) => (
                    <div key={draft.channel} className="draft-card">
                      <div className="draft-header">
                        <div className="draft-channel">
                          {draft.channel === 'email' && '📧'} {draft.channel === 'sms' && '💬'}
                          {draft.channel === 'linkedin' && '💼'} {draft.channel === 'instagram' && '📷'}
                          {draft.channel === 'whatsapp' && '📱'}
                          {' '}{draft.channel}
                        </div>
                        {draft.score !== undefined && (
                          <div className={`draft-score ${draft.score < 7 ? 'low' : ''}`}>
                            {draft.score.toFixed(1)}/10
                          </div>
                        )}
                      </div>
                      
                      {draft.subject && (
                        <div className="draft-subject">
                          <strong>Subject:</strong> {draft.subject}
                        </div>
                      )}
                      
                      <div className="draft-body">{draft.body}</div>
                      
                      {campaign.current_stage === 'approval' && (
                        <div className="draft-actions">
                          <button
                            className={`btn-approve ${approvalChoices[draft.channel] === 'approve' ? 'active' : ''}`}
                            onClick={() => handleDraftAction(draft.channel, 'approve')}
                          >
                            ✓ Approve
                          </button>
                          <button
                            className={`btn-regen ${approvalChoices[draft.channel] === 'regen' ? 'active' : ''}`}
                            onClick={() => handleDraftAction(draft.channel, 'regen')}
                          >
                            ↻ Regen
                          </button>
                          <button
                            className={`btn-skip ${approvalChoices[draft.channel] === 'skip' ? 'active' : ''}`}
                            onClick={() => handleDraftAction(draft.channel, 'skip')}
                          >
                            ✗ Skip
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                
                {campaign.current_stage === 'approval' && Object.keys(approvalChoices).length > 0 && (
                  <button className="btn-primary" style={{ marginTop: '20px' }} onClick={handleSubmitApprovals}>
                    Submit Choices →
                  </button>
                )}

                {/* Show Complete Campaign button once choices have been applied */}
                {campaign.current_stage === 'approval' && Object.keys(approvalChoices).length === 0 && campaign.drafts.some(d => d.approved || d.body.includes('[SKIPPED]') || d.body.includes('Regenerated')) && (
                  <button className="btn-primary" style={{ marginTop: '20px' }} onClick={handleCompleteCampaign}>
                    ✓ Complete Campaign
                  </button>
                )}
              </div>
            )}

            {campaign.status === 'completed' && (
              <div className="completion-card">
                <div className="completion-icon">✓</div>
                <h2>Campaign Completed Successfully</h2>
                <p>All approved messages have been sent to their respective channels.</p>
                <button 
                  className="btn-secondary" 
                  style={{ marginTop: '20px', maxWidth: '300px', margin: '20px auto 0' }} 
                  onClick={() => {
                    if (pollingInterval) {
                      clearInterval(pollingInterval);
                      setPollingInterval(null);
                    }
                    setCampaign(null);
                    setUrlInput('');
                    setTextInput('');
                    setFile(null);
                    setApprovalChoices({});
                  }}
                >
                  Start New Campaign
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default App;
