"use client";

import React, { useState } from 'react';
import { useParams } from 'next/navigation';
import { Card, CardHeader } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badge';
import { Search, ArrowDown, Sparkles, Loader2, GitMerge } from 'lucide-react';

export default function FeatureTracingPage() {
  const params = useParams();
  const repoName = params.repoName as string;
  
  const [query, setQuery] = useState('');
  const [isTracing, setIsTracing] = useState(false);
  const [traceResult, setTraceResult] = useState<any>(null);
  const [contextPack, setContextPack] = useState<any>(null);
  
  const [isExplaining, setIsExplaining] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);

  const handleTrace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setIsTracing(true);
    setTraceResult(null);
    setContextPack(null);
    setExplanation(null);
    
    try {
      const [traceRes, contextRes] = await Promise.all([
        fetch(`/api/repos/${repoName}/trace?q=${encodeURIComponent(query)}`),
        fetch(`/api/repos/${repoName}/context?q=${encodeURIComponent(query)}`)
      ]);

      if (traceRes.ok) {
        const data = await traceRes.json();
        setTraceResult(data.trace);
      } else {
        alert("Failed to generate trace.");
      }

      if (contextRes.ok) {
        const data = await contextRes.json();
        setContextPack(data.context_pack);
      }
    } catch (err) {
      console.error(err);
      alert("Error fetching trace.");
    } finally {
      setIsTracing(false);
    }
  };

  const handleExplain = async () => {
    if (!traceResult) return;
    
    setIsExplaining(true);
    try {
      const res = await fetch(`/api/repos/${repoName}/trace/explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          feature_query: query,
          trace_data: traceResult
        })
      });
      if (res.ok) {
        const data = await res.json();
        setExplanation(data.explanation);
      } else {
        alert("Failed to explain trace.");
      }
    } catch (err) {
      console.error(err);
      alert("Error fetching explanation.");
    } finally {
      setIsExplaining(false);
    }
  };

  return (
    <div className="p-8 w-full max-w-5xl mx-auto flex flex-col h-full overflow-y-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
          <GitMerge className="w-8 h-8 text-blue-600" />
          Feature Tracing
        </h1>
        <p className="text-slate-500 mt-2">
          Deterministically reconstruct the implementation flow of a feature across the repository.
        </p>
      </div>

      <Card className="mb-8">
        <div className="p-6">
          <form onSubmit={handleTrace} className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter a feature name (e.g., Authentication, Login, Payment)"
                className="w-full pl-10 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-colors"
                disabled={isTracing}
              />
            </div>
            <Button 
              type="submit" 
              variant="primary" 
              disabled={isTracing || !query.trim()}
              className="px-6"
            >
              {isTracing ? <Loader2 className="w-5 h-5 animate-spin" /> : "Trace Feature"}
            </Button>
          </form>
        </div>
      </Card>

      {traceResult && traceResult.flow && traceResult.flow.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-slate-800">Implementation Path</h2>
              <Badge variant="info">{traceResult.flow.length} Nodes</Badge>
            </div>
            
            <div className="space-y-2 relative">
              <div className="absolute left-6 top-6 bottom-6 w-0.5 bg-blue-100"></div>
              
              {traceResult.flow.map((node: any, idx: number) => (
                <div key={node.id} className="relative z-10 flex flex-col items-center">
                  <div className="w-full flex items-start gap-4 group">
                    <div className="w-12 h-12 rounded-full bg-blue-50 border-4 border-white shadow-sm flex items-center justify-center flex-shrink-0 z-10 text-blue-600 font-bold">
                      {idx + 1}
                    </div>
                    <Card className="flex-1 hover:shadow-md transition-shadow cursor-pointer">
                      <div className="p-4">
                        <div className="flex justify-between items-start mb-2">
                          <h3 className="font-bold text-slate-800 text-lg">{node.name}</h3>
                          <Badge variant="neutral">{node.type}</Badge>
                        </div>
                        <p className="text-sm text-slate-500 font-mono truncate">{node.file_id}</p>
                      </div>
                    </Card>
                  </div>
                  {idx < traceResult.flow.length - 1 && (
                    <div className="py-2 text-blue-300">
                      <ArrowDown className="w-6 h-6" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
          
          <div className="lg:col-span-1">
            <div className="sticky top-8 space-y-6">
              <Card>
                <CardHeader title="Graph-Aware Context" />
                <div className="p-6 space-y-4">
                  {contextPack ? (
                    <>
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div className="rounded-lg border border-slate-200 p-3">
                          <p className="text-xs uppercase tracking-wider text-slate-500">Features</p>
                          <p className="text-lg font-bold text-slate-900">{contextPack.repository?.feature_count ?? 0}</p>
                        </div>
                        <div className="rounded-lg border border-slate-200 p-3">
                          <p className="text-xs uppercase tracking-wider text-slate-500">Symbols</p>
                          <p className="text-lg font-bold text-slate-900">{contextPack.repository?.symbol_count ?? 0}</p>
                        </div>
                      </div>

                      <div>
                        <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">Top Features</p>
                        <div className="space-y-2">
                          {(contextPack.features || []).slice(0, 3).map((feature: any) => (
                            <div key={feature.id} className="rounded-lg bg-slate-50 border border-slate-200 p-3">
                              <div className="flex items-center justify-between gap-3">
                                <div>
                                  <p className="text-sm font-medium text-slate-900">{feature.name}</p>
                                  <p className="text-xs text-slate-500">{feature.member_count} members</p>
                                </div>
                                <Badge variant="neutral">{Math.round((feature.confidence || 0) * 100)}%</Badge>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {(contextPack.matched_symbols || []).length > 0 && (
                        <div>
                          <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">Matched Symbols</p>
                          <div className="space-y-2">
                            {contextPack.matched_symbols.slice(0, 3).map((symbol: any) => (
                              <div key={symbol.id} className="rounded-lg border border-slate-200 p-3">
                                <p className="text-sm font-medium text-slate-900">{symbol.name}</p>
                                <p className="text-xs text-slate-500 font-mono truncate">{symbol.file}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="text-center py-6">
                      <Sparkles className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                      <p className="text-slate-500 text-sm">Build a context pack to summarize features, symbols, and graph neighbors.</p>
                    </div>
                  )}
                </div>
              </Card>

              <Card>
                <CardHeader title="AI Explanation" />
                <div className="p-6">
                  {!explanation ? (
                    <div className="text-center py-8">
                      <Sparkles className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                      <p className="text-slate-500 mb-6 text-sm">
                        Understand how these components work together to implement the feature.
                      </p>
                      <Button 
                        variant="secondary" 
                        onClick={handleExplain}
                        disabled={isExplaining || !traceResult}
                        className="w-full"
                      >
                        {isExplaining ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Sparkles className="w-4 h-4 mr-2" />}
                        Explain Trace
                      </Button>
                    </div>
                  ) : (
                    <div className="prose prose-sm prose-slate max-w-none">
                      <div className="bg-blue-50 text-blue-900 p-4 rounded-lg text-sm leading-relaxed whitespace-pre-wrap">
                        {explanation}
                      </div>
                      <Button 
                        variant="ghost" 
                        onClick={handleExplain}
                        disabled={isExplaining}
                        className="w-full mt-4 text-xs"
                      >
                        Regenerate
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}
      
      {traceResult && (!traceResult.flow || traceResult.flow.length === 0) && (
        <div className="text-center py-20 text-slate-500">
          <p>No deterministic trace could be constructed for this feature.</p>
        </div>
      )}
    </div>
  );
}
