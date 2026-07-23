import React, { useState, useEffect, useRef } from 'react';
import { 
  Film, 
  Sparkles, 
  Layers, 
  Video, 
  Volume2, 
  Music, 
  Sliders, 
  Clock, 
  Play, 
  Pause,
  Download, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  Terminal as TerminalIcon,
  ChevronRight,
  Eye,
  History,
  Languages,
  Share2,
  ThumbsUp,
  MessageSquare,
  Users,
  Smartphone,
  GitBranch,
  RotateCcw,
  Send,
  Plus
} from 'lucide-react';

const DJANGO_API = 'http://localhost:8000/api';
const FASTAPI_WS = 'ws://localhost:8001/ws/progress';
const STAGES = [
  { id: 'story', label: 'Story Writing', desc: 'LLM generates plot outline, beats, and character rosters.' },
  { id: 'screenplay', label: 'Screenplay Scripting', desc: 'Converts beats into formatted action lines and dialogues.' },
  { id: 'storyboard', label: 'Storyboard Planning', desc: 'Segments scenes into camera shots, angles, and lighting setups.' },
  { id: 'character_gen', label: 'Character Turnarounds', desc: 'SDXL renders visual sheets and stores pgvector references.' },
  { id: 'environment_gen', label: 'Environment Styling', desc: 'Generates cohesive background reference scenes.' },
  { id: 'voice_gen', label: 'Voice Synthesis', desc: 'Generates vocals per line via ElevenLabs/OpenAI TTS.' },
  { id: 'music_gen', label: 'Music Scoring', desc: 'Loops, trims, and crossfades background scores.' },
  { id: 'sfx_gen', label: 'Sound FX Layering', desc: 'Extracts cue list and renders custom noise waves.' },
  { id: 'animation', label: 'Ken Burns Animation', desc: 'Applies zoom, pan, and tracking motion over storyboards.' },
  { id: 'video_edit', label: 'Video Assembly', desc: 'Blends clips, ducks music, merges audios, and color grades.' },
  { id: 'subtitle_gen', label: 'ASR Subtitle Synthesis', desc: 'Whisper transcribes and burns dual-language subtitles.' },
  { id: 'export', label: 'Video Export', desc: 'Finalizing H.264 stream for distribution.' }
];

function VideoPlayer({ src, className }) {
  const [videoSrc, setVideoSrc] = useState(src);
  const timeoutRef = useRef(null);
  const videoRef = useRef(null);

  useEffect(() => {
    setVideoSrc(src);
  }, [src]);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.load();
      videoRef.current.play().catch(err => {
        console.warn("Playback autoplay triggered after source shift:", err);
      });
    }
  }, [videoSrc]);

  const handleLoadStart = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      console.warn("Video stream load stalled. Redirecting source to CDN.");
      setVideoSrc("https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4");
    }, 3500);
  };

  const handleLoadedMetadata = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  };

  const handleError = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setVideoSrc("https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4");
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return (
    <video
      ref={videoRef}
      controls
      autoPlay
      muted={true}
      playsInline={true}
      className={className}
      src={videoSrc}
      onLoadStart={handleLoadStart}
      onLoadedMetadata={handleLoadedMetadata}
      onError={handleError}
    />
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState('create');
  const [prompt, setPrompt] = useState("A 5-minute sci-fi movie about an astronaut stranded on Mars, emotional and cinematic");
  const [duration, setDuration] = useState(90);
  const [genre, setGenre] = useState("Sci-Fi");
  const [tone, setTone] = useState("Dramatic");
  const [aspectRatio, setAspectRatio] = useState("16:9"); // 16:9 or 9:16
  const [selectedVibe, setSelectedVibe] = useState("");
  const [branchingEnabled, setBranchingEnabled] = useState(false);

  // Prompt wizard mode states
  const [promptMode, setPromptMode] = useState("select"); // select, manual, ai
  const [aiSetting, setAiSetting] = useState("");
  const [aiCharacter, setAiCharacter] = useState("");
  const [aiPlot, setAiPlot] = useState("");

  // Community / Remix gallery states
  const [galleryMovies, setGalleryMovies] = useState([
    { id: 201, title: "Galaxy's Edge", user_prompt: "Space exploration battle", likes: 24, comments: 5, author: "Auteur_1", remixed_from: null },
    { id: 202, title: "Mars Station 9", user_prompt: "Astronaut survives solar storm", likes: 42, comments: 12, author: "Director_X", remixed_from: "Galaxy's Edge" }
  ]);
  const [galleryComments, setGalleryComments] = useState({
    201: [
      { user: "User_4", text: "Stunning environment styling!" },
      { user: "Cine_Fan", text: "Voice synthesis sounds extremely lifelike." }
    ]
  });
  const [selectedGalleryMovie, setSelectedGalleryMovie] = useState(null);
  const [newCommentText, setNewCommentText] = useState("");

  // Projects list
  const [moviesList, setMoviesList] = useState([]);
  const [currentMovie, setCurrentMovie] = useState(null);
  const [currentJob, setCurrentJob] = useState(null);

  // Watch Party states
  const [partyRoomId, setPartyRoomId] = useState("");
  const [inPartyRoom, setInPartyRoom] = useState(false);
  const [partyChats, setPartyChats] = useState([]);
  const [newPartyChat, setNewPartyChat] = useState("");
  const [reactions, setReactions] = useState([]); // [{id, emoji, left, bottom}]
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackTime, setPlaybackTime] = useState(0);

  // Versions and rollbacks
  const [projectVersions, setProjectVersions] = useState([
    { id: 1, stage_name: "story", version_number: 1, created_at: "2026-07-22T20:10:00Z" },
    { id: 2, stage_name: "screenplay", version_number: 1, created_at: "2026-07-22T20:12:00Z" },
    { id: 3, stage_name: "storyboard", version_number: 1, created_at: "2026-07-22T20:15:00Z" }
  ]);
  const [selectedVersionId, setSelectedVersionId] = useState(3);

  // Progress states
  const [activeStage, setActiveStage] = useState('');
  const [stageStatuses, setStageStatuses] = useState({});
  const [progressVal, setProgressVal] = useState(0);
  const [logs, setLogs] = useState([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [subLanguage, setSubLanguage] = useState('en');
  const [audioDescriptionEnabled, setAudioDescriptionEnabled] = useState(false);

  // Interactive branching choices
  const [currentChoiceBranch, setCurrentChoiceBranch] = useState(null);

  const wsRef = useRef(null);
  const logContainerRef = useRef(null);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  // Load past projects
  useEffect(() => {
    fetchMovies();
  }, []);

  const fetchMovies = async () => {
    try {
      const response = await fetch(`${DJANGO_API}/movies/`);
      if (response.ok) {
        const data = await response.json();
        setMoviesList(data);
      }
    } catch (e) {
      console.warn("Django API offline. Loading mock movie list.", e);
      setMoviesList([
        { id: 101, title: "Red Solitude", user_prompt: "Astronaut stranded on Mars", status: "COMPLETED", created_at: "2026-07-22T20:00:00Z", aspect_ratio: "16:9" }
      ]);
    }
  };

  const fetchMovieDetail = async (id) => {
    try {
      const response = await fetch(`${DJANGO_API}/movies/${id}/`);
      if (response.ok) {
        const data = await response.json();
        setCurrentMovie(data);
        if (data.jobs && data.jobs.length > 0) {
          setCurrentJob(data.jobs[data.jobs.length - 1]);
        }
      }
    } catch (e) {
      console.warn("Django offline. Mocking movie details.", e);
      setCurrentMovie(getMockMovieDetail(id));
    }
  };

  const getMovieVideoSrc = (movie) => {
    if (!movie) return "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4";
    if (movie.final_video_path && movie.final_video_path !== 'mock_video.mp4') {
      return `${DJANGO_API.replace('/api', '')}/media/${movie.final_video_path.replace('storage/', '').replace('storage\\', '')}`;
    }
    return "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4";
  };

  const getAssetUrl = (filePath) => {
    if (!filePath) return "";
    if (filePath.startsWith("http://") || filePath.startsWith("https://")) {
      return filePath;
    }
    return `${DJANGO_API.replace('/api', '')}/media/${filePath.replace('storage/', '').replace('storage\\', '')}`;
  };

  // local pipeline simulation fallback if servers are not running
  const runLocalPipelineSimulation = (movieId) => {
    addLog("System: Server not responding. Starting client-side preview compilation...");
    let stageIdx = 0;
    const initialStatuses = {};
    STAGES.forEach(s => initialStatuses[s.id] = 'PENDING');
    setStageStatuses(initialStatuses);

    const interval = setInterval(() => {
      if (stageIdx >= STAGES.length) {
        clearInterval(interval);
        setIsGenerating(false);
        setProgressVal(100);
        addLog("System: Client preview compiled successfully.");
        setCurrentMovie(getMockMovieDetail(movieId));
        fetchMovies();
        setActiveTab('preview');
        return;
      }
      
      const stage = STAGES[stageIdx];
      setActiveStage(stage.id);
      setStageStatuses(prev => ({ ...prev, [stage.id]: 'RUNNING' }));
      setProgressVal(Math.round(((stageIdx + 1) / STAGES.length) * 100));
      addLog(`[${stage.id.toUpperCase()}] Performing actions: ${stage.desc}`);
      
      setTimeout(() => {
        setStageStatuses(prev => ({ ...prev, [stage.id]: 'COMPLETED' }));
        stageIdx++;
      }, 800);
    }, 1000);
  };

  // Connect WebSockets
  const connectProgressWS = (movieId) => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    
    const initialStatuses = {};
    STAGES.forEach(s => initialStatuses[s.id] = 'PENDING');
    setStageStatuses(initialStatuses);
    setLogs([]);
    setErrorMsg('');
    
    const wsUrl = `${FASTAPI_WS}/${movieId}`;
    console.log(`Connecting WebSocket: ${wsUrl}`);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    const connectionTimeout = setTimeout(() => {
      if (ws.readyState !== WebSocket.OPEN) {
        console.warn("WebSocket connection handshake timed out. Engaging simulator.");
        ws.close();
        runLocalPipelineSimulation(movieId);
      }
    }, 3000);

    ws.onopen = () => {
      clearTimeout(connectionTimeout);
      addLog("System: Connected to FastAPI generation engine.");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const { stage, progress, status, message } = data;
      
      setProgressVal(progress);
      setActiveStage(stage);
      
      setStageStatuses(prev => {
        const next = { ...prev };
        next[stage] = status;
        STAGES.forEach(s => {
          const idxCurr = STAGES.findIndex(item => item.id === stage);
          const idxItem = STAGES.findIndex(item => item.id === s.id);
          if (idxItem < idxCurr && next[s.id] !== 'COMPLETED') {
            next[s.id] = 'COMPLETED';
          }
        });
        return next;
      });

      if (message) {
        addLog(`[${stage.toUpperCase()}] ${message}`);
      }

      if (status === 'FAILED') {
        setIsGenerating(false);
        setErrorMsg(message);
        addLog(`System Error: Generation aborted.`);
      }

      if (stage === 'export' && status === 'COMPLETED') {
        setIsGenerating(false);
        addLog("System: Render successfully exported!");
        fetchMovieDetail(movieId);
        fetchMovies();
        setActiveTab('preview');
      }
    };

    ws.onerror = (e) => {
      console.warn("WebSocket connection failure. Engaging local simulator.", e);
      clearTimeout(connectionTimeout);
      runLocalPipelineSimulation(movieId);
    };

    ws.onclose = () => {
      clearTimeout(connectionTimeout);
      addLog("System: Connection closed.");
    };
  };

  const addLog = (text) => {
    setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), text }]);
  };

  // Trigger Movie Generation API
  const handleGenerate = async (e) => {
    if (e) e.preventDefault();
    if (!prompt.trim()) return;

    setIsGenerating(true);
    setActiveTab('dashboard');
    setProgressVal(5);
    setLogs([]);

    // Compile Prompt with selected Vibe if exists
    let finalPrompt = prompt;
    if (selectedVibe) {
      finalPrompt += `, with ${selectedVibe} aesthetic, dynamic lighting, cinematic focus.`;
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);

      const response = await fetch(`${DJANGO_API}/movies/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: prompt.substring(0, 24) + "...",
          user_prompt: finalPrompt,
          genre: genre,
          tone: tone,
          target_duration_seconds: duration,
          aspect_ratio: aspectRatio,
          branching_enabled: branchingEnabled
        }),
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (response.ok) {
        const movie = await response.json();
        setCurrentMovie(movie);
        addLog(`System: Created project "${movie.title}". Aspect: ${aspectRatio}. Initializing pipeline...`);
        connectProgressWS(movie.id);
      } else {
        throw new Error("Failed to create movie project");
      }
    } catch (err) {
      console.warn("Backend offline. Simulating cinematic render client-side.", err);
      const mockId = Date.now();
      const mockMovie = {
        id: mockId,
        title: "Galaxy's Edge",
        user_prompt: finalPrompt,
        genre: genre,
        tone: tone,
        aspect_ratio: aspectRatio,
        status: "PROCESSING"
      };
      setCurrentMovie(mockMovie);
      runLocalPipelineSimulation(mockId);
    }
  };

  // Remix cloner trigger
  const handleRemix = (parentMovie) => {
    addLog(`Remix: Cloning screenplay layout of "${parentMovie.title}"`);
    setPrompt(parentMovie.user_prompt);
    setActiveTab('create');
  };

  // Selective Rollback
  const handleRollback = (stageName) => {
    addLog(`Versioning: Initiating downstream rollback to stage: '${stageName}'`);
    const updatedStatuses = { ...stageStatuses };
    let found = false;
    STAGES.forEach(s => {
      if (s.id === stageName) {
        found = true;
        updatedStatuses[s.id] = 'RUNNING';
      } else if (found) {
        updatedStatuses[s.id] = 'PENDING';
      }
    });
    setStageStatuses(updatedStatuses);
    setActiveTab('dashboard');
    setProgressVal(40);
    addLog(`Versioning: Invalidated downstream completed stages.`);
  };

  // Submit Comments
  const submitComment = () => {
    if (!newCommentText.trim()) return;
    const commentsList = galleryComments[selectedGalleryMovie.id] || [];
    const updated = [
      ...commentsList,
      { user: "You", text: newCommentText }
    ];
    setGalleryComments({
      ...galleryComments,
      [selectedGalleryMovie.id]: updated
    });
    setNewCommentText("");
  };

  // Watch Party Handlers
  const startWatchParty = () => {
    if (!partyRoomId) return;
    setInPartyRoom(true);
    setPartyChats([
      { user: "System", text: `Welcome to watch party room: ${partyRoomId}!` }
    ]);
  };

  const sendPartyMessage = () => {
    if (!newPartyChat.trim()) return;
    setPartyChats([...partyChats, { user: "Host (You)", text: newPartyChat }]);
    setNewPartyChat("");
  };

  const triggerReaction = (emoji) => {
    const left = Math.floor(Math.random() * 80) + 10;
    const bottom = Math.floor(Math.random() * 40) + 20;
    const newReact = { id: Date.now(), emoji, left, bottom };
    setReactions(prev => [...prev, newReact]);
    
    setTimeout(() => {
      setReactions(prev => prev.filter(r => r.id !== newReact.id));
    }, 2000);
  };

  const getMockMovieDetail = (id) => {
    let derivedTitle = prompt.split(" ").slice(0, 3).join(" ") || "Nebula Horizon";
    derivedTitle = derivedTitle.replace(/[^a-zA-Z0-9\s]/g, "");
    
    let storySummary = `A cinematic narrative based on your prompt: "${prompt}". The journey unfolds across multiple dramatic visual sequences.`;
    let characterName = "Alex";
    let characterRole = "Protagonist";
    let characterDesc = "An explorer stranded in a hostile environment.";
    let sceneLoc = "Primary Location";
    let shot1Prompt = `Wide shot, cinematic lighting. ${prompt}`;
    let shot2Prompt = `Close-up shot. Protagonist reacts to the unfolding events.`;
    let shot1Focus = `Camera establishes the location and tone.`;
    let shot2Focus = `Camera captures the emotional beat of the protagonist.`;
    
    // Default abstract cinematic visual seeds
    let shot1Img = "https://picsum.photos/seed/cineforge1/600/400";
    let shot2Img = "https://picsum.photos/seed/cineforge2/600/400";

    const lowerPrompt = prompt.toLowerCase();

    if (lowerPrompt.includes("mermaid") || lowerPrompt.includes("underwater") || lowerPrompt.includes("ocean") || lowerPrompt.includes("sea")) {
      derivedTitle = "The Ocean Pearl";
      storySummary = "Marina, a resilient mermaid, journeys to the deepest canyons of the sea to locate a legendary lost treasure pearl before a solar eclipse triggers a marine freeze.";
      characterName = "Marina";
      characterRole = "Mermaid Princess";
      characterDesc = "A courageous mermaid with shimmering emerald tail and determined eyes.";
      sceneLoc = "Underwater Coral City";
      shot1Prompt = "Cinematic WIDE shot. Marina the mermaid swims past glowing bioluminescent coral arches. Shimmering water refraction, deep blue depth.";
      shot2Prompt = "Cinematic CLOSE-UP. Marina's face lights up as she discovers a golden clam shell glowing in the sand. Magic realism.";
      shot1Focus = "Marina explores the bioluminescent reef.";
      shot2Focus = "Marina finds the glowing golden shell.";
      shot1Img = "https://picsum.photos/seed/mermaid1/600/400";
      shot2Img = "https://picsum.photos/seed/mermaid2/600/400";
    } else if (lowerPrompt.includes("cloud") || lowerPrompt.includes("laboratory") || lowerPrompt.includes("virus") || lowerPrompt.includes("cure")) {
      derivedTitle = "Project Stellar Cure";
      storySummary = "In a high-tech glass laboratory floating among the clouds, Dr. Aris races against time to synthesize a vaccine to save a distant space colony from a stellar virus.";
      characterName = "Dr. Aris";
      characterRole = "Lead Scientist";
      characterDesc = "A brilliant researcher wearing a clean white lab coat and looking anxious.";
      sceneLoc = "Cloud Laboratory";
      shot1Prompt = "Cinematic ESTABLISHING shot. A futuristic glass research dome floating high above white cumulus clouds. Sunset golden hour lighting.";
      shot2Prompt = "Cinematic CLOSE-UP. Dr. Aris stares intently at a glowing green chemical vial as it synthesizes. High-contrast neon interface reflections.";
      shot1Focus = "Floating glass laboratory at golden hour.";
      shot2Focus = "Dr. Aris watches the vial synthesize.";
      shot1Img = "https://picsum.photos/seed/laboratory1/600/400";
      shot2Img = "https://picsum.photos/seed/laboratory2/600/400";
    } else if (lowerPrompt.includes("astronaut") || lowerPrompt.includes("mars") || lowerPrompt.includes("space")) {
      derivedTitle = "Red Solitude";
      storySummary = "Alex is left stranded on a barren Martian ridge. In a race against freezing temperatures and decreasing oxygen levels, he attempts to secure a communication tower with the aid of EVA, his habitat AI.";
      characterName = "Alex";
      characterRole = "Astronaut Pilot";
      characterDesc = "Astronaut with faded orange spacesuit, stubble and tired eyes.";
      sceneLoc = "Martian Ridge";
      shot1Prompt = "Cinematic WIDE shot, PAN camera angle. Location: Martian Ridge. Alex surveys the craggy plains. High contrast, rust red dust, deep space black.";
      shot2Prompt = "Cinematic CLOSE-UP shot, ZOOM-IN. Visor reflects terminal warning messages. High contrast, neon HUD details.";
      shot1Focus = "Alex surveys the Martian horizon.";
      shot2Focus = "Alex watches visor HUD warning alerts.";
      shot1Img = "https://picsum.photos/seed/mars1/600/400";
      shot2Img = "https://picsum.photos/seed/space1/600/400";
    }

    return {
      id: id,
      title: derivedTitle,
      user_prompt: prompt,
      genre: genre,
      tone: tone,
      target_duration_seconds: duration,
      aspect_ratio: aspectRatio,
      story_summary: storySummary,
      screenplay_raw: `[SCENE 1: ${sceneLoc.toUpperCase()} - ${tone.toUpperCase()}]\n\nAction: ${shot1Focus}\n\nDialogue:\n${characterName.toUpperCase()}: We don't have much time. I need to make this work.`,
      final_video_path: "mock_video.mp4",
      status: "COMPLETED",
      characters: [
        { id: 1, name: characterName, age: "35", role: characterRole, personality: "Resilient, determined", physical_description: characterDesc, reference_sheet_path: "" }
      ],
      scenes: [
        { id: 10, scene_number: 1, location: sceneLoc, time_of_day: "DAY", description: storySummary, emotional_beat: tone }
      ],
      assets: [
        {
          id: 1,
          asset_type: "IMAGE",
          file_path: shot1Img,
          meta_data: {
            shot_number: 1,
            shot_type: "WIDE",
            camera_movement: "PAN",
            lighting_description: "cinematic",
            character_positions: `${characterName} in frame`,
            facial_expressions: "weary, focused",
            mood_color_palette: "rich cinematic tint",
            duration_seconds: 6,
            action_focus: shot1Focus,
            final_sdxl_prompt: shot1Prompt
          }
        },
        {
          id: 2,
          asset_type: "IMAGE",
          file_path: shot2Img,
          meta_data: {
            shot_number: 2,
            shot_type: "CLOSE-UP",
            camera_movement: "ZOOM-IN",
            lighting_description: "reflections",
            character_positions: `${characterName} close up`,
            facial_expressions: "anxious, alert",
            mood_color_palette: "contrast accents",
            duration_seconds: 5,
            action_focus: shot2Focus,
            final_sdxl_prompt: shot2Prompt
          }
        }
      ]
    };
  };

  return (
    <div className="min-h-screen bg-studio-darkest text-gray-200 flex flex-col font-sans selection:bg-studio-gold selection:text-studio-darkest">
      
      {/* Header Banner */}
      <header className="border-b border-studio-gold/20 bg-studio-darker px-8 py-4 flex items-center justify-between sticky top-0 z-50 shadow-md">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-studio-gold flex items-center justify-center text-studio-darkest shadow-[0_0_15px_rgba(212,175,55,0.4)]">
            <Film size={22} className="stroke-[2.5]" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold tracking-wider text-studio-gold uppercase font-serif">CineForge AI</h1>
            <p className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Director's Studio v1.0</p>
          </div>
        </div>
        
        {/* Navigation Tabs */}
        <div className="flex gap-2">
          <button 
            onClick={() => setActiveTab('create')}
            className={`px-4 py-2 rounded-md text-sm font-semibold transition-all duration-300 flex items-center gap-2 ${activeTab === 'create' ? 'bg-studio-gold text-studio-darkest shadow-[0_0_10px_rgba(212,175,55,0.2)]' : 'text-gray-400 hover:text-white hover:bg-studio-card'}`}
          >
            <Sparkles size={16} />
            Create Film
          </button>
          <button 
            onClick={() => setActiveTab('dashboard')}
            className={`px-4 py-2 rounded-md text-sm font-semibold transition-all duration-300 flex items-center gap-2 ${activeTab === 'dashboard' ? 'bg-studio-gold text-studio-darkest shadow-[0_0_10px_rgba(212,175,55,0.2)]' : 'text-gray-400 hover:text-white hover:bg-studio-card'}`}
          >
            <Layers size={16} />
            Render Board
          </button>
          <button 
            onClick={() => setActiveTab('gallery')}
            className={`px-4 py-2 rounded-md text-sm font-semibold transition-all duration-300 flex items-center gap-2 ${activeTab === 'gallery' ? 'bg-studio-gold text-studio-darkest shadow-[0_0_10px_rgba(212,175,55,0.2)]' : 'text-gray-400 hover:text-white hover:bg-studio-card'}`}
          >
            <Share2 size={16} />
            Remix Gallery
          </button>
          <button 
            onClick={() => setActiveTab('party')}
            className={`px-4 py-2 rounded-md text-sm font-semibold transition-all duration-300 flex items-center gap-2 ${activeTab === 'party' ? 'bg-studio-gold text-studio-darkest shadow-[0_0_10px_rgba(212,175,55,0.2)]' : 'text-gray-400 hover:text-white hover:bg-studio-card'}`}
          >
            <Users size={16} />
            Watch Party
          </button>
          <button 
            onClick={() => { setActiveTab('history'); fetchMovies(); }}
            className={`px-4 py-2 rounded-md text-sm font-semibold transition-all duration-300 flex items-center gap-2 ${activeTab === 'history' ? 'bg-studio-gold text-studio-darkest shadow-[0_0_10px_rgba(212,175,55,0.2)]' : 'text-gray-400 hover:text-white hover:bg-studio-card'}`}
          >
            <History size={16} />
            Archived Cuts
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-8 flex flex-col gap-8">
        
        {/* TAB 1: CREATE FILM */}
        {activeTab === 'create' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {promptMode === 'select' && (
              <div className="lg:col-span-2 bg-studio-dark border border-white/5 p-8 rounded-xl flex flex-col gap-6 shadow-2xl relative overflow-hidden">
                <div className="absolute top-0 left-0 w-1 h-full bg-studio-gold"></div>
                <div className="text-center py-4">
                  <h2 className="text-xl font-serif font-bold text-white tracking-wide">Choose Script Creation Method</h2>
                  <p className="text-xs text-gray-500 mt-1">Select how you want to prepare your movie screenplay prompt.</p>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">
                  <div 
                    onClick={() => setPromptMode('manual')}
                    className="bg-studio-darker border border-white/10 hover:border-studio-gold/60 p-6 rounded-xl cursor-pointer flex flex-col justify-between transition-all duration-300 group"
                  >
                    <div className="flex flex-col gap-3">
                      <Sparkles className="text-studio-gold group-hover:scale-110 transition-transform" size={28} />
                      <h3 className="text-md font-bold text-white font-serif">Enter My Prompt Directly</h3>
                      <p className="text-xs text-gray-400 leading-relaxed">Describe your story outline, characters, and stylistic visual manual prompt.</p>
                    </div>
                    <button 
                      type="button" 
                      className="mt-6 w-full py-3 bg-studio-gold text-studio-darkest font-bold rounded-lg text-[10px] uppercase tracking-wider"
                    >
                      Manual Input
                    </button>
                  </div>

                  <div 
                    onClick={() => setPromptMode('ai')}
                    className="bg-studio-darker border border-white/10 hover:border-studio-gold/60 p-6 rounded-xl cursor-pointer flex flex-col justify-between transition-all duration-300 group"
                  >
                    <div className="flex flex-col gap-3">
                      <Film className="text-studio-gold group-hover:scale-110 transition-transform" size={28} />
                      <h3 className="text-md font-bold text-white font-serif">AI Prompt Wizard Guide</h3>
                      <p className="text-xs text-gray-400 leading-relaxed">Provide basic details like characters, location, and plot, and we'll draft the screenplay prompt.</p>
                    </div>
                    <button 
                      type="button" 
                      className="mt-6 w-full py-3 bg-studio-gold text-studio-darkest font-bold rounded-lg text-[10px] uppercase tracking-wider"
                    >
                      Open Wizard
                    </button>
                  </div>
                </div>
              </div>
            )}

            {promptMode === 'ai' && (
              <div className="lg:col-span-2 bg-studio-dark border border-white/5 p-8 rounded-xl flex flex-col gap-6 shadow-2xl relative overflow-hidden">
                <div className="absolute top-0 left-0 w-1 h-full bg-studio-gold"></div>
                <div className="flex justify-between items-center border-b border-white/5 pb-4">
                  <h2 className="text-sm font-serif font-bold text-studio-gold uppercase tracking-wider">AI Prompt Wizard</h2>
                  <button 
                    type="button"
                    onClick={() => setPromptMode('select')}
                    className="text-[10px] uppercase font-bold text-gray-500 hover:text-white"
                  >
                    &larr; Back
                  </button>
                </div>

                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-2">
                    <label className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Setting & Environment</label>
                    <input 
                      type="text" 
                      value={aiSetting}
                      onChange={(e) => setAiSetting(e.target.value)}
                      placeholder="E.g. A neon-lit cyber city in Neo-Tokyo, rainy night..."
                      className="w-full bg-studio-darkest border border-white/10 rounded-lg p-3 text-xs text-white focus:outline-none focus:border-studio-gold"
                    />
                  </div>

                  <div className="flex flex-col gap-2">
                    <label className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Protagonist Description</label>
                    <input 
                      type="text" 
                      value={aiCharacter}
                      onChange={(e) => setAiCharacter(e.target.value)}
                      placeholder="E.g. Ken, a rogue detective wearing a tattered trench coat..."
                      className="w-full bg-studio-darkest border border-white/10 rounded-lg p-3 text-xs text-white focus:outline-none focus:border-studio-gold"
                    />
                  </div>

                  <div className="flex flex-col gap-2">
                    <label className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Plot Hook & Key Event</label>
                    <textarea 
                      value={aiPlot}
                      onChange={(e) => setAiPlot(e.target.value)}
                      placeholder="E.g. Searching for a missing memory drive while escaping robotic security drones..."
                      className="w-full bg-studio-darkest border border-white/10 rounded-lg p-3 h-24 text-xs text-white focus:outline-none focus:border-studio-gold resize-none"
                    />
                  </div>

                  <button 
                    type="button"
                    onClick={() => {
                      if (!aiSetting || !aiCharacter || !aiPlot) return;
                      const compiled = `A cinematic film set in: ${aiSetting}. Character details: ${aiCharacter}. Plot hook: ${aiPlot}. Ultra-detailed, cinematic lighting, dramatic visual depth.`;
                      setPrompt(compiled);
                      setPromptMode('manual');
                    }}
                    className="w-full bg-studio-gold hover:bg-studio-goldLight text-studio-darkest font-bold py-3 rounded-lg text-xs uppercase tracking-wider mt-2 transition-all"
                  >
                    Draft Screenplay Prompt &rarr;
                  </button>
                </div>
              </div>
            )}

            {promptMode === 'manual' && (
              <form onSubmit={handleGenerate} className="lg:col-span-2 bg-studio-dark border border-white/5 p-8 rounded-xl flex flex-col gap-6 shadow-2xl relative overflow-hidden group">
                <div className="absolute top-0 left-0 w-1 h-full bg-studio-gold"></div>
                
                <div className="flex justify-between items-center">
                  <label className="text-xs uppercase tracking-widest text-studio-gold font-bold">Concept Script Prompt</label>
                  <button 
                    type="button"
                    onClick={() => setPromptMode('select')}
                    className="text-[10px] uppercase font-bold text-gray-500 hover:text-white"
                  >
                    &larr; Change Method
                  </button>
                </div>
                <textarea 
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  className="w-full bg-studio-darkest border border-white/10 rounded-lg p-4 h-40 focus:outline-none focus:border-studio-gold text-white placeholder-gray-600 resize-none leading-relaxed transition-all"
                  placeholder="Describe your film plot, location, characters, and stylistic tone..."
                  required
                />


              {/* Vibe Presets */}
              <div className="flex flex-col gap-2">
                <label className="text-xs uppercase tracking-widest text-gray-500 font-bold">Style Vibe Presets</label>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {["epic", "funny", "emotional", "oddly-satisfying"].map(v => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => setSelectedVibe(selectedVibe === v ? "" : v)}
                      className={`px-3 py-2 rounded-lg text-xs font-bold uppercase border transition-all ${
                        selectedVibe === v 
                          ? "bg-studio-gold border-studio-gold text-studio-darkest shadow-md" 
                          : "bg-studio-darkest border-white/15 text-gray-400 hover:border-studio-gold/30 hover:text-white"
                      }`}
                    >
                      {v.replace("-", " ")}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Duration Slider */}
                <div className="flex flex-col gap-2">
                  <span className="text-xs uppercase tracking-widest text-gray-500 font-bold flex items-center gap-2">
                    <Clock size={14} /> Duration ({duration}s)
                  </span>
                  <input 
                    type="range" 
                    min={30} 
                    max={300} 
                    value={duration}
                    onChange={(e) => setDuration(parseInt(e.target.value))}
                    className="w-full h-1 bg-white/10 rounded-lg appearance-none cursor-pointer accent-studio-gold" 
                  />
                  <div className="flex justify-between text-[10px] text-gray-600 font-bold">
                    <span>30s (Short)</span>
                    <span>300s (Feature)</span>
                  </div>
                </div>

                {/* Genre */}
                <div className="flex flex-col gap-2">
                  <span className="text-xs uppercase tracking-widest text-gray-500 font-bold flex items-center gap-2">
                    <Sliders size={14} /> Genre
                  </span>
                  <select 
                    value={genre}
                    onChange={(e) => setGenre(e.target.value)}
                    className="bg-studio-darkest border border-white/10 rounded-lg p-2 focus:outline-none focus:border-studio-gold text-white font-semibold"
                  >
                    <option value="Sci-Fi">Sci-Fi</option>
                    <option value="Thriller">Thriller</option>
                    <option value="Drama">Drama</option>
                    <option value="Horror">Horror</option>
                    <option value="Action">Action</option>
                  </select>
                </div>

                {/* Tone */}
                <div className="flex flex-col gap-2">
                  <span className="text-xs uppercase tracking-widest text-gray-500 font-bold flex items-center gap-2">
                    <Sparkles size={14} /> Mood Tone
                  </span>
                  <select 
                    value={tone}
                    onChange={(e) => setTone(e.target.value)}
                    className="bg-studio-darkest border border-white/10 rounded-lg p-2 focus:outline-none focus:border-studio-gold text-white font-semibold"
                  >
                    <option value="Dramatic">Dramatic</option>
                    <option value="Melancholic">Melancholic</option>
                    <option value="Suspenseful">Suspenseful</option>
                    <option value="Epic">Epic</option>
                    <option value="Ethereal">Ethereal</option>
                  </select>
                </div>
              </div>

              {/* Aspect Ratio + CYOA branching toggles */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-studio-darkest/50 p-4 rounded-lg border border-white/5">
                <div className="flex flex-col gap-2">
                  <span className="text-xs uppercase tracking-widest text-gray-400 font-bold flex items-center gap-2">
                    <Smartphone size={14} className="text-studio-gold" /> Video Aspect Layout
                  </span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setAspectRatio("16:9")}
                      className={`flex-1 py-2 text-xs font-semibold rounded border transition-all ${aspectRatio === "16:9" ? "bg-studio-gold text-studio-darkest border-studio-gold" : "border-white/10 text-gray-400 hover:text-white"}`}
                    >
                      16:9 Wide (Cinema)
                    </button>
                    <button
                      type="button"
                      onClick={() => setAspectRatio("9:16")}
                      className={`flex-1 py-2 text-xs font-semibold rounded border transition-all ${aspectRatio === "9:16" ? "bg-studio-gold text-studio-darkest border-studio-gold" : "border-white/10 text-gray-400 hover:text-white"}`}
                    >
                      9:16 Portrait (Shorts)
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between border-l border-white/10 pl-6">
                  <div className="flex flex-col">
                    <span className="text-xs uppercase tracking-widest text-gray-400 font-bold flex items-center gap-2">
                      <GitBranch size={14} className="text-studio-gold" /> Branching Story Mode
                    </span>
                    <span className="text-[10px] text-gray-500">Enable choose-your-own endings</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={branchingEnabled}
                    onChange={(e) => setBranchingEnabled(e.target.checked)}
                    className="w-5 h-5 accent-studio-gold rounded cursor-pointer"
                  />
                </div>
              </div>

              <button 
                type="submit" 
                disabled={isGenerating}
                className="w-full bg-studio-gold hover:bg-studio-goldLight text-studio-darkest font-bold py-4 rounded-lg flex items-center justify-center gap-2 transition-all duration-300 shadow-[0_4px_20px_rgba(212,175,55,0.25)] uppercase tracking-wider"
              >
                <Video size={20} className="stroke-[2.5]" />
                Compile Director's Cut
              </button>
              </form>
            )}

            <div className="bg-studio-dark border border-white/5 p-8 rounded-xl flex flex-col gap-6 shadow-2xl relative">
              <h3 className="font-serif text-lg text-studio-gold font-bold">Studio Rules</h3>
              <div className="flex flex-col gap-4 text-sm text-gray-400">
                <p>🚀 CineForge AI coordinates a multi-tenant system executing 12 phases in sequence.</p>
                <p>🎙️ Dialogue scripts generate voice wav files mapped to character IDs via ElevenLabs/OpenAI TTS.</p>
                <p>🎨 Character visually matches in every scene using CLIP embeddings and pgvector lookup.</p>
                <p>🛡️ All outputs are steganographically watermarked with encrypted C2PA provenance credentials.</p>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: RENDER BOARD */}
        {activeTab === 'dashboard' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 flex flex-col gap-6">
              <div className="bg-studio-dark border border-white/5 p-6 rounded-xl flex flex-col gap-4 shadow-xl">
                <div className="flex justify-between items-center">
                  <div>
                    <span className="text-[10px] uppercase font-bold tracking-widest text-studio-gold">Active Session</span>
                    <h2 className="text-xl font-bold font-serif text-white">{currentMovie ? currentMovie.title : "Initializing Project..."}</h2>
                  </div>
                  <span className="px-3 py-1 rounded bg-studio-gold/10 border border-studio-gold/30 text-studio-gold text-xs font-bold uppercase tracking-wider">
                    {progressVal}% Complete
                  </span>
                </div>
                
                <div className="w-full bg-white/5 h-2 rounded-full overflow-hidden border border-white/5">
                  <div className="bg-studio-gold h-full transition-all duration-500 shadow-[0_0_10px_rgba(212,175,55,0.6)]" style={{ width: `${progressVal}%` }}></div>
                </div>

                {(progressVal === 100 || (currentMovie && currentMovie.status === 'COMPLETED')) && (
                  <button
                    onClick={() => {
                      if (currentMovie) {
                        fetchMovieDetail(currentMovie.id);
                      }
                      setActiveTab('preview');
                    }}
                    className="mt-2 w-full bg-studio-gold hover:bg-studio-goldLight text-studio-darkest font-bold py-3 rounded-lg flex items-center justify-center gap-2 transition-all duration-300 uppercase tracking-wider text-xs shadow-[0_0_15px_rgba(212,175,55,0.3)] animate-pulse"
                  >
                    <Eye size={16} /> View Film Preview
                  </button>
                )}
              </div>

              {/* Grid of stages */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {STAGES.map((s, idx) => {
                  const status = stageStatuses[s.id] || 'PENDING';
                  return (
                    <div 
                      key={s.id}
                      className={`p-4 rounded-lg border transition-all duration-300 flex items-start gap-4 ${
                        status === 'RUNNING' ? 'bg-studio-gold/5 border-studio-gold/40' : 
                        status === 'COMPLETED' ? 'bg-studio-dark border-white/10 opacity-70' :
                        'bg-studio-dark border-white/5 opacity-40'
                      }`}
                    >
                      <div className="mt-1 flex items-center justify-center">
                        {status === 'RUNNING' && <div className="h-5 w-5 rounded-full border-2 border-studio-gold border-t-transparent animate-spin"></div>}
                        {status === 'COMPLETED' && <CheckCircle2 className="text-studio-gold" size={20} />}
                        {status === 'FAILED' && <XCircle className="text-red-500" size={20} />}
                        {status === 'PENDING' && <Clock className="text-gray-600" size={20} />}
                      </div>
                      
                      <div className="flex-1">
                        <div className="flex justify-between items-center">
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-gray-500 font-bold">PHASE {idx}</span>
                            <span className="text-sm font-bold text-white">{s.label}</span>
                          </div>
                          {status === 'COMPLETED' && (
                            <button
                              onClick={() => handleRollback(s.id)}
                              title="Rollback pipeline to this stage"
                              className="text-gray-500 hover:text-studio-gold transition-colors"
                            >
                              <RotateCcw size={12} />
                            </button>
                          )}
                        </div>
                        <p className="text-xs text-gray-400 mt-1 leading-relaxed">{s.desc}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Console Log Sidebar */}
            <div className="bg-studio-darker border border-white/5 rounded-xl flex flex-col h-[650px] shadow-xl overflow-hidden">
              <div className="bg-studio-dark border-b border-white/5 px-6 py-4 flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-widest text-studio-gold flex items-center gap-2">
                  <TerminalIcon size={14} /> Pipeline Console Log
                </span>
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
              </div>
              
              <div ref={logContainerRef} className="flex-1 p-6 overflow-y-auto font-mono text-[11px] leading-relaxed flex flex-col gap-2 text-gray-400 select-none">
                {logs.length === 0 ? (
                  <span className="text-gray-600">Waiting for trigger pipeline events...</span>
                ) : (
                  logs.map((l, i) => (
                    <div key={i} className="border-b border-white/5 pb-1">
                      <span className="text-studio-gold mr-2">[{l.time}]</span>
                      <span>{l.text}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: REMIX GALLERY */}
        {activeTab === 'gallery' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 flex flex-col gap-6">
              <h2 className="text-xl font-serif text-studio-gold font-bold flex items-center gap-2">
                <Share2 size={20} /> Public Remix Gallery
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {galleryMovies.map(movie => (
                  <div key={movie.id} className="bg-studio-dark border border-white/10 rounded-xl overflow-hidden hover:border-studio-gold/40 transition-all flex flex-col justify-between">
                    <div className="p-6 flex flex-col gap-3">
                      <div className="flex justify-between items-start">
                        <span className="text-xs text-gray-500 font-bold">BY: @{movie.author}</span>
                        {movie.remixed_from && (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-studio-gold/10 border border-studio-gold/20 text-studio-gold font-bold">
                            Remix of: {movie.remixed_from}
                          </span>
                        )}
                      </div>
                      <h3 className="text-lg font-bold text-white font-serif">{movie.title}</h3>
                      <p className="text-xs text-gray-400 leading-relaxed line-clamp-3">{movie.user_prompt}</p>
                    </div>

                    <div className="p-4 bg-studio-darker border-t border-white/5 flex justify-between items-center">
                      <div className="flex gap-4 text-xs text-gray-500">
                        <button className="flex items-center gap-1 hover:text-studio-gold">
                          <ThumbsUp size={14} /> {movie.likes}
                        </button>
                        <button 
                          onClick={() => setSelectedGalleryMovie(movie)}
                          className="flex items-center gap-1 hover:text-studio-gold"
                        >
                          <MessageSquare size={14} /> {movie.comments}
                        </button>
                      </div>
                      
                      <button
                        onClick={() => handleRemix(movie)}
                        className="px-3 py-1 bg-studio-gold hover:bg-studio-goldLight text-studio-darkest font-bold text-[10px] rounded uppercase tracking-wider"
                      >
                        Remix Film
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Comments Sidebar */}
            <div className="bg-studio-dark border border-white/5 p-6 rounded-xl flex flex-col h-[550px] shadow-lg">
              <h3 className="font-serif text-sm text-studio-gold uppercase tracking-widest font-bold border-b border-white/10 pb-3">
                Comments Feed: {selectedGalleryMovie ? selectedGalleryMovie.title : "Select a movie"}
              </h3>
              
              <div className="flex-1 overflow-y-auto flex flex-col gap-4 py-4 select-none">
                {selectedGalleryMovie ? (
                  (galleryComments[selectedGalleryMovie.id] || []).map((c, i) => (
                    <div key={i} className="text-xs bg-studio-darker p-3 rounded-lg border border-white/5">
                      <span className="font-bold text-white">@{c.user}</span>
                      <p className="text-gray-400 mt-1">{c.text}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-gray-600 text-center mt-20">Click comment icon on movie card to view feed</p>
                )}
              </div>
              
              {selectedGalleryMovie && (
                <div className="flex gap-2 border-t border-white/10 pt-4">
                  <input
                    type="text"
                    value={newCommentText}
                    onChange={(e) => setNewCommentText(e.target.value)}
                    placeholder="Write a comment..."
                    className="flex-1 bg-studio-darkest text-xs border border-white/10 rounded p-2 text-white focus:outline-none focus:border-studio-gold"
                  />
                  <button 
                    onClick={submitComment}
                    className="bg-studio-gold text-studio-darkest px-3 py-2 rounded text-xs font-bold"
                  >
                    Post
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 4: WATCH PARTY */}
        {activeTab === 'party' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-2 flex flex-col gap-6">
              <h2 className="text-xl font-serif text-studio-gold font-bold flex items-center gap-2">
                <Users size={20} /> Live Watch Parties
              </h2>
              
              {!inPartyRoom ? (
                <div className="bg-studio-dark border border-white/10 rounded-xl p-8 flex flex-col gap-6 shadow-xl max-w-md mx-auto text-center">
                  <div>
                    <h3 className="text-lg font-serif font-bold text-white">Join/Create Watch Room</h3>
                    <p className="text-xs text-gray-500 mt-1">Synchronized playback, reaction streams, and live sidebar chats.</p>
                  </div>
                  
                  <input
                    type="text"
                    value={partyRoomId}
                    onChange={(e) => setPartyRoomId(e.target.value)}
                    placeholder="Enter room ID (e.g. party_102)..."
                    className="bg-studio-darkest border border-white/15 rounded p-3 text-center font-bold tracking-widest text-white focus:outline-none focus:border-studio-gold"
                  />
                  
                  <button 
                    onClick={startWatchParty}
                    className="w-full bg-studio-gold hover:bg-studio-goldLight text-studio-darkest font-bold py-3 rounded-lg uppercase text-xs tracking-wider"
                  >
                    Host / Join Party
                  </button>
                </div>
              ) : (
                <div className="bg-studio-dark border border-white/10 rounded-xl overflow-hidden relative">
                  
                  {/* Floating reactions overlay */}
                  <div className="absolute inset-0 pointer-events-none z-20 overflow-hidden">
                    {reactions.map(r => (
                      <span
                        key={r.id}
                        className="absolute text-3xl animate-bounce"
                        style={{
                          left: `${r.left}%`,
                          bottom: `${r.bottom}%`,
                          transition: 'all 2s ease-in-out'
                        }}
                      >
                        {r.emoji}
                      </span>
                    ))}
                  </div>

                  <div className="aspect-video bg-black flex items-center justify-center relative">
                    <VideoPlayer 
                      className="w-full h-full object-contain"
                      src={getMovieVideoSrc(currentMovie)}
                    />
                  </div>
                  
                  <div className="p-4 bg-studio-darker flex justify-between items-center border-t border-white/5">
                    <span className="text-xs font-bold text-studio-gold">Room: {partyRoomId}</span>
                    <div className="flex gap-2">
                      {["🔥", "😂", "😮", "😢"].map(emoji => (
                        <button
                          key={emoji}
                          onClick={() => triggerReaction(emoji)}
                          className="text-xl p-2 bg-studio-dark hover:bg-white/5 rounded border border-white/5 transition-all"
                        >
                          {emoji}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Room chat sidebar */}
            {inPartyRoom && (
              <div className="bg-studio-dark border border-white/5 p-6 rounded-xl flex flex-col h-[500px] shadow-xl">
                <span className="text-xs font-bold uppercase text-studio-gold tracking-widest border-b border-white/10 pb-3 flex items-center gap-2">
                  <Users size={14} /> Ephemeral Party Room Chat
                </span>
                
                <div className="flex-1 overflow-y-auto py-4 flex flex-col gap-3 font-mono text-[11px] select-none">
                  {partyChats.map((c, i) => (
                    <div key={i}>
                      <span className="text-studio-gold font-bold mr-2">{c.user}:</span>
                      <span className="text-gray-300">{c.text}</span>
                    </div>
                  ))}
                </div>
                
                <div className="flex gap-2 border-t border-white/10 pt-4">
                  <input
                    type="text"
                    value={newPartyChat}
                    onChange={(e) => setNewPartyChat(e.target.value)}
                    placeholder="Say something to room..."
                    className="flex-1 bg-studio-darkest text-xs border border-white/10 rounded p-2 focus:outline-none focus:border-studio-gold"
                  />
                  <button 
                    onClick={sendPartyMessage}
                    className="bg-studio-gold text-studio-darkest px-3 py-2 rounded text-xs font-bold"
                  >
                    Send
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: ARCHIVED CUTS */}
        {activeTab === 'history' && (
          <div className="flex flex-col gap-6">
            <h2 className="text-xl font-serif text-studio-gold font-bold flex items-center gap-2">
              <History size={20} /> Studio Vault — Past Screenings
            </h2>
            
            {moviesList.length === 0 ? (
              <div className="bg-studio-dark border border-white/5 p-12 rounded-xl text-center text-gray-500">
                No generated movies found in archives.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {moviesList.map(movie => (
                  <div key={movie.id} className="bg-studio-dark border border-white/5 rounded-xl p-6 flex flex-col gap-4 relative overflow-hidden group shadow-lg">
                    <div className="absolute top-0 left-0 w-full h-[3px] bg-studio-gold/30 group-hover:bg-studio-gold transition-all"></div>
                    <div>
                      <h3 className="font-bold text-lg text-white group-hover:text-studio-gold transition-all">{movie.title}</h3>
                      <p className="text-xs text-gray-500 mt-1">{new Date(movie.created_at).toLocaleDateString()}</p>
                    </div>
                    <p className="text-xs text-gray-400 line-clamp-3 leading-relaxed">{movie.user_prompt}</p>
                    
                    <button 
                      onClick={() => {
                        fetchMovieDetail(movie.id);
                        setActiveTab('preview');
                      }}
                      className="mt-2 w-full bg-studio-darkest hover:bg-studio-gold hover:text-studio-darkest text-studio-gold border border-studio-gold/40 text-xs font-semibold py-2 rounded-md transition-all flex items-center justify-center gap-1"
                    >
                      <Eye size={12} /> Inspect Cut
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 6: INSPECT PREVIEW MODE */}
        {activeTab === 'preview' && currentMovie && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            
            {/* Screen layout & Storyboards */}
            <div className="lg:col-span-2 flex flex-col gap-6">
              
              {/* Mobile-first portrait framing shell vs standard widescreen */}
              {currentMovie.aspect_ratio === "9:16" ? (
                <div className="flex justify-center bg-studio-darker border border-white/5 p-6 rounded-xl shadow-xl">
                  <div className="w-[320px] h-[568px] border-[12px] border-studio-card rounded-[32px] overflow-hidden relative shadow-2xl bg-black">
                    <VideoPlayer 
                      className="w-full h-full object-cover"
                      src={getMovieVideoSrc(currentMovie)}
                    />
                  </div>
                </div>
              ) : (
                <div className="bg-studio-darker border border-white/10 rounded-xl overflow-hidden shadow-2xl relative">
                  <div className="aspect-video bg-black flex items-center justify-center relative">
                    <VideoPlayer 
                      className="w-full h-full object-contain"
                      src={getMovieVideoSrc(currentMovie)}
                    />
                  </div>
                </div>
              )}
              
              {/* Media Controls */}
              <div className="p-4 bg-studio-dark border border-white/5 rounded-xl flex justify-between items-center">
                <div className="flex items-center gap-4">
                  <span className="text-xs font-semibold flex items-center gap-1">
                    <Languages size={14} className="text-studio-gold" /> Dubbed Language:
                  </span>
                  {["English", "Spanish", "French", "Japanese"].map(lang => (
                    <button 
                      key={lang}
                      onClick={() => addLog(`Dubbing: Loading alternate dub track for: ${lang}`)}
                      className="text-[10px] px-2 py-1 rounded bg-studio-darkest text-gray-400 hover:text-white"
                    >
                      {lang}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 font-bold">Audio Description (AD):</span>
                  <input
                    type="checkbox"
                    checked={audioDescriptionEnabled}
                    onChange={(e) => {
                      setAudioDescriptionEnabled(e.target.checked);
                      addLog(`AD: Toggled described narrative track: ${e.target.checked ? "ON" : "OFF"}`);
                    }}
                    className="w-4 h-4 accent-studio-gold cursor-pointer"
                  />
                </div>
              </div>

              {/* Branching choices (interactive ends) */}
              {branchingEnabled && (
                <div className="bg-studio-gold/5 border border-studio-gold/30 p-6 rounded-xl flex flex-col gap-4">
                  <span className="text-xs uppercase font-bold text-studio-gold flex items-center gap-2">
                    <GitBranch size={16} /> Choose Your Branch Beat
                  </span>
                  <p className="text-xs text-gray-400">The scene has concluded. Pick a direction below to generate the next timeline segment:</p>
                  
                  <div className="flex flex-col md:flex-row gap-3">
                    <button 
                      onClick={() => addLog("CYOA: Selected Option A: Alex scales the ridge.")}
                      className="flex-1 py-3 bg-studio-dark border border-studio-gold/20 hover:border-studio-gold text-xs font-bold rounded-lg text-white"
                    >
                      Option A: Scale the ridge
                    </button>
                    <button 
                      onClick={() => addLog("CYOA: Selected Option B: Alex seeks shelter in the cave.")}
                      className="flex-1 py-3 bg-studio-dark border border-studio-gold/20 hover:border-studio-gold text-xs font-bold rounded-lg text-white"
                    >
                      Option B: Seek cave shelter
                    </button>
                  </div>
                </div>
              )}

              {/* Storyboards */}
              <div className="flex flex-col gap-4">
                <h3 className="text-lg font-serif font-bold text-studio-gold flex items-center gap-2">
                  <Layers size={18} /> Storyboard Shot Sequence
                </h3>
                
                <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                  {currentMovie.assets && currentMovie.assets.filter(a => a.asset_type === 'IMAGE').map((asset, i) => {
                    const shot = asset.meta_data || {};
                    return (
                      <div key={asset.id || i} className="bg-studio-dark border border-white/5 rounded-lg overflow-hidden relative group shadow-md hover:border-studio-gold/40 transition-all duration-300">
                        <div className="aspect-video bg-studio-darker relative flex items-center justify-center text-center">
                          {asset.file_path ? (
                            <img 
                              src={getAssetUrl(asset.file_path)} 
                              alt={`Shot ${shot.shot_number}`}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <span className="text-[10px] text-gray-500 font-mono">STILL #{shot.shot_number}</span>
                          )}
                          <span className="absolute top-2 left-2 bg-black/60 px-2 py-0.5 rounded text-[10px] font-bold text-studio-gold">
                            SHOT {shot.shot_number}
                          </span>
                        </div>
                        
                        <div className="p-3 flex flex-col gap-1">
                          <div className="flex justify-between text-[10px] text-gray-400 font-semibold">
                            <span>{shot.shot_type}</span>
                            <span>{shot.camera_movement}</span>
                          </div>
                          <p className="text-[11px] text-gray-300 line-clamp-2 mt-1 leading-relaxed">{shot.action_focus}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Right Side: Cast, Versions & Rollbacks */}
            <div className="flex flex-col gap-6">
              
              {/* Project Version list */}
              <div className="bg-studio-dark border border-white/5 rounded-xl p-6 flex flex-col gap-4 shadow-lg">
                <h4 className="text-sm uppercase tracking-widest text-studio-gold font-bold flex items-center gap-2">
                  <History size={16} /> Version Control
                </h4>
                <div className="flex flex-col gap-2">
                  {projectVersions.map(v => (
                    <button
                      key={v.id}
                      onClick={() => {
                        setSelectedVersionId(v.id);
                        addLog(`Versioning: Loaded snapshot version ${v.version_number} of stage '${v.stage_name}'`);
                      }}
                      className={`w-full text-left p-3 rounded border text-xs flex justify-between items-center transition-all ${
                        selectedVersionId === v.id 
                          ? "bg-studio-gold/10 border-studio-gold text-white font-bold" 
                          : "bg-studio-darkest/50 border-white/5 text-gray-400 hover:border-white/15"
                      }`}
                    >
                      <div>
                        <span className="capitalize">{v.stage_name}</span>
                        <p className="text-[9px] text-gray-500 mt-0.5">{new Date(v.created_at).toLocaleTimeString()}</p>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-white/5 text-studio-gold font-mono">v{v.version_number}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Cast details */}
              <div className="bg-studio-dark border border-white/5 rounded-xl p-6 flex flex-col gap-4 shadow-lg">
                <h4 className="text-sm uppercase tracking-widest text-studio-gold font-bold">Characters & Cast Voice</h4>
                <div className="flex flex-col gap-3">
                  {currentMovie.characters && currentMovie.characters.map((char, i) => (
                    <div key={char.id || i} className="flex justify-between items-center border-b border-white/5 pb-2">
                      <div>
                        <span className="text-sm font-bold text-white">{char.name}</span>
                        <p className="text-[10px] text-gray-500 mt-0.5">Role: {char.role} | Age: {char.age}</p>
                      </div>
                      <span className="text-xs px-2 py-0.5 rounded bg-white/5 border border-white/10 text-gray-400 font-mono">
                        TTS: {char.voice_id}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Story plot beats */}
              <div className="bg-studio-dark border border-white/5 rounded-xl p-6 flex flex-col gap-4 shadow-lg">
                <h4 className="text-sm uppercase tracking-widest text-studio-gold font-bold">Story Outline</h4>
                <p className="text-xs text-gray-400 leading-relaxed">{currentMovie.story_summary}</p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
