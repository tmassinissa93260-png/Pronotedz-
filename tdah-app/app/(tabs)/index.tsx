import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  Pressable,
  SectionList,
  StyleSheet,
  ActivityIndicator,
  Alert,
  Modal,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import { useRouter } from 'expo-router';
import { supabase } from '../../lib/supabase/client';
import { breakdownTask } from '../../lib/ai/breakdownTask';
import { planFromBraindump, planWeekFromBraindump } from '../../lib/ai/braindump';
import { interpretScheduleCommand } from '../../lib/ai/scheduleAssistant';
import { generateGhostReply } from '../../lib/ai/ghostReply';
import { getHighDreadMomentStats, type MomentStats } from '../../lib/supabase/momentStats';
import { usePremiumGate } from '../../lib/billing/stripe';
import { useAiQuota } from '../../lib/billing/aiQuota';
import { spacing, fonts, radius, shadow, makeTypography, makeGradients, type ThemeColors } from '../../constants/theme';
import { LinearGradient } from 'expo-linear-gradient';
import { useTheme } from '../../lib/theme/ThemeProvider';
import { useAuth } from '../../lib/supabase/AuthProvider';
import { useProfile } from '../../lib/supabase/useProfile';
import { bumpStreak } from '../../lib/supabase/streak';
import { maybeUnlockFirstTaskBadge } from '../../lib/supabase/badges';
import { ensureRoutinesForToday } from '../../lib/supabase/routines';
import { useReward } from '../../lib/rewards/RewardProvider';
import { InteroceptionCheckIn } from '../../components/InteroceptionCheckIn';
import { TimelineView } from '../../components/TimelineView';
import { syncTaskToCalendar } from '../../lib/calendar/sync';
import { resolveTaskIcon, ICON_CHOICES, COLOR_CHOICES } from '../../lib/taskIcon';
import { scheduleTaskReminder, cancelTaskReminder } from '../../lib/notifications';

type Subtask = { id: string; titre: string; fait: boolean; ordre: number };
type MomentJournee = 'n_importe_quand' | 'matin' | 'jour' | 'soir';
type Task = {
  id: string;
  titre: string;
  statut: 'a_faire' | 'en_cours' | 'fait' | 'reporte';
  estimation_minutes: number | null;
  temps_reel_minutes: number | null;
  moment_journee: MomentJournee;
  niveau_dread: number | null;
  niveau_priorite: 'haute' | 'moyenne' | 'basse' | null;
  heure_debut: string | null;
  ordre: number;
  icone_manuelle: string | null;
  couleur_manuelle: string | null;
  si_alors: string | null;
  cout_energie: 'faible' | 'moyen' | 'eleve' | null;
  subtasks: Subtask[];
};

const today = () => new Date().toISOString().slice(0, 10);
const GRANULARITE_LABELS: Record<1 | 2 | 3, string> = { 1: 'Grandes lignes', 2: 'Standard', 3: 'Petits pas' };
const PRIORITE_CYCLE: (Task['niveau_priorite'])[] = [null, 'haute', 'moyenne', 'basse'];
function prioriteColors(colors: ThemeColors): Record<'haute' | 'moyenne' | 'basse', string> {
  return {
    haute: colors.danger,
    moyenne: colors.warning,
    basse: colors.textMuted,
  };
}
const MOMENT_LABELS: Record<MomentJournee, string> = {
  n_importe_quand: 'N’importe quand',
  matin: 'Matin',
  jour: 'Jour',
  soir: 'Soir',
};
const MOMENT_ORDER: MomentJournee[] = ['n_importe_quand', 'matin', 'jour', 'soir'];
const WEEKDAY_LETTERS = ['L', 'M', 'M', 'J', 'V', 'S', 'D'];

function mondayOf(dateISO: string) {
  const d = new Date(`${dateISO}T00:00:00`);
  const day = d.getDay() || 7;
  d.setDate(d.getDate() - day + 1);
  return d;
}

export default function AccueilScreen() {
  const { session } = useAuth();
  const router = useRouter();
  const profile = useProfile();
  const { celebrate } = useReward();
  const { colors, focusMode } = useTheme();
  const styles = useMemo(() => makeStyles(colors), [colors]);
  const gradients = useMemo(() => makeGradients(colors), [colors]);
  const PRIORITE_COLOR = useMemo(() => prioriteColors(colors), [colors]);
  const { isPremium, gate, statut } = usePremiumGate();
  const { canUse: aiQuotaOk, remaining: aiRemaining, limit: aiLimit, recordUsage: markAiUsage } = useAiQuota();
  const [nudgeDismissed, setNudgeDismissed] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [estimationInput, setEstimationInput] = useState<Record<string, string>>({});
  const [timeInput, setTimeInput] = useState<Record<string, string>>({});
  const [siAlorsEditId, setSiAlorsEditId] = useState<string | null>(null);
  const [siAlorsInput, setSiAlorsInput] = useState<Record<string, string>>({});
  const [decomposingId, setDecomposingId] = useState<string | null>(null);
  const [granulariteByTask, setGranulariteByTask] = useState<Record<string, 1 | 2 | 3>>({});
  const [checkInVisible, setCheckInVisible] = useState(false);
  const [openedAt] = useState(Date.now());
  const [braindumpVisible, setBraindumpVisible] = useState(false);
  const [braindumpText, setBraindumpText] = useState('');
  const [braindumpLoading, setBraindumpLoading] = useState(false);
  const [braindumpScope, setBraindumpScope] = useState<'jour' | 'semaine'>('jour');
  const [vueMode, setVueMode] = useState<'liste' | 'timeline'>('liste');
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({});
  const [streakDays, setStreakDays] = useState<number | null>(null);
  const [selectedDate, setSelectedDate] = useState(() => today());
  const [momentStats, setMomentStats] = useState<MomentStats | null>(null);
  const [retardPickerVisible, setRetardPickerVisible] = useState(false);
  const [iconPickerTaskId, setIconPickerTaskId] = useState<string | null>(null);
  const [pickerColor, setPickerColor] = useState(COLOR_CHOICES[0]);
  const [overflowTask, setOverflowTask] = useState<Task | null>(null);
  const [assistantVisible, setAssistantVisible] = useState(false);
  const [assistantInput, setAssistantInput] = useState('');
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantMessages, setAssistantMessages] = useState<{ role: 'user' | 'assistant'; text: string }[]>([]);
  const [toolsMenuVisible, setToolsMenuVisible] = useState(false);
  const [modeCrashVisible, setModeCrashVisible] = useState(false);
  const [ghostReplyVisible, setGhostReplyVisible] = useState(false);
  const [ghostReplyContext, setGhostReplyContext] = useState('');
  const [ghostReplyLoading, setGhostReplyLoading] = useState(false);
  const [ghostReplyResult, setGhostReplyResult] = useState('');
  const [retourApresPauseVisible, setRetourApresPauseVisible] = useState(false);
  const [joursAbsence, setJoursAbsence] = useState(0);
  const retourPauseShownRef = useRef(false);

  const loadTasks = useCallback(async () => {
    if (!session) return;
    setIsLoading(true);
    try {
      // Les routines ne se matérialisent que pour le vrai "aujourd'hui" —
      // pas de sens à en créer pour un jour futur qu'on ne fait que consulter.
      if (selectedDate === today()) {
        await ensureRoutinesForToday(session.user.id);
      }
      const { data, error } = await supabase
        .from('tasks')
        .select('id, titre, statut, estimation_minutes, temps_reel_minutes, moment_journee, niveau_dread, niveau_priorite, heure_debut, ordre, icone_manuelle, couleur_manuelle, si_alors, cout_energie, subtasks(id, titre, fait, ordre)')
        .eq('date_prevue', selectedDate)
        .order('ordre', { ascending: true })
        .order('created_at', { ascending: true });

      if (error) throw error;
      setTasks((data as unknown as Task[]) ?? []);
    } catch (e) {
      // Connexion instable ou requête en échec : on ne bloque jamais l'écran
      // sur un spinner infini, l'utilisateur garde au moins l'écran vide/précédent.
      Alert.alert('Connexion impossible', 'Impossible de charger tes tâches pour le moment. Réessaie dans un instant.');
    } finally {
      setIsLoading(false);
    }
  }, [session, selectedDate]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    if (!session) return;
    supabase
      .from('streaks')
      .select('jours_consecutifs, derniere_activite')
      .eq('user_id', session.user.id)
      .single()
      .then(({ data }) => {
        setStreakDays(data?.jours_consecutifs ?? null);
        // "Rétention par le pardon" : après une longue absence, un compteur
        // cassé et des notifications rouges poussent à désinstaller plutôt
        // qu'à revenir — un seul message chaleureux, une seule fois par
        // ouverture, jamais répété à chaque rafraîchissement.
        if (data?.derniere_activite && !retourPauseShownRef.current) {
          const derniere = new Date(`${data.derniere_activite}T00:00:00`);
          const jours = Math.floor((Date.now() - derniere.getTime()) / (24 * 60 * 60 * 1000));
          if (jours >= 4) {
            retourPauseShownRef.current = true;
            setJoursAbsence(jours);
            setRetourApresPauseVisible(true);
          }
        }
      });
  }, [session, tasks]);

  // Coach proactif : on regarde si les tâches très angoissantes passées ont
  // vraiment été menées à terme selon le moment de journée choisi, pour
  // avertir dès la création plutôt que de laisser le pattern se répéter en
  // silence — sans appel IA, juste une agrégation de l'historique.
  useEffect(() => {
    if (!session) return;
    getHighDreadMomentStats(session.user.id).then(setMomentStats);
  }, [session, tasks]);

  // Rappels locaux 5 min avant l'heure prévue — uniquement pour "aujourd'hui",
  // pas de sens de programmer un rappel pour un jour qu'on ne fait que
  // consulter. Répond au point le plus cité dans les checklists "bonne app
  // ADHD" : des rappels pour respecter les horaires sans y penser sans arrêt.
  useEffect(() => {
    if (selectedDate !== today()) return;
    for (const t of tasks) {
      if (t.heure_debut && t.statut !== 'fait') {
        scheduleTaskReminder(t.id, t.titre, selectedDate, t.heure_debut);
      }
    }
  }, [tasks, selectedDate]);

  // Check-in d'interoception discret après un long moment passé sur l'écran
  // du planning (proxy simple pour "session de travail prolongée" en V1 —
  // sera affiné en V2 avec la détection de surcharge par wearable).
  useEffect(() => {
    const timer = setTimeout(() => setCheckInVisible(true), 90 * 60 * 1000);
    return () => clearTimeout(timer);
  }, [openedAt]);

  // Calibration temporelle active : moyenne des écarts estimation/réel sur
  // les tâches déjà closes, pour donner un vrai insight, pas juste stocker.
  const calibrationInsight = useMemo(() => {
    const withBoth = tasks.filter((t) => t.estimation_minutes && t.temps_reel_minutes);
    if (withBoth.length < 3) return null;
    const ratio =
      withBoth.reduce((sum, t) => sum + t.temps_reel_minutes! / t.estimation_minutes!, 0) / withBoth.length;
    if (ratio < 1.15) return null; // pas d'écart notable, pas besoin de le dire
    return `Tu mets en moyenne ${ratio.toFixed(1)}x plus de temps que prévu — pense à multiplier tes estimations.`;
  }, [tasks]);

  // Regroupement par moment de journée (façon Tiimo) — moins de bruit qu'une
  // liste plate, un utilisateur voit tout de suite ce qui presse ce matin.
  const sections = useMemo(() => {
    return MOMENT_ORDER.map((moment) => {
      const full = tasks.filter((t) => (t.moment_journee ?? 'n_importe_quand') === moment);
      return { moment, title: MOMENT_LABELS[moment], count: full.length, data: collapsedSections[moment] ? [] : full };
    }).filter((s) => s.count > 0);
  }, [tasks, collapsedSections]);

  function toggleSection(moment: MomentJournee) {
    setCollapsedSections((prev) => ({ ...prev, [moment]: !prev[moment] }));
  }

  // Sélecteur de jour en semaine (façon Tiimo) : naviguer entre les jours au
  // lieu d'être bloqué sur "aujourd'hui" — pratique pour préparer demain le
  // soir, ou revoir ce qui était prévu hier.
  const weekDays = useMemo(() => {
    const monday = mondayOf(selectedDate);
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      return d.toISOString().slice(0, 10);
    });
  }, [selectedDate]);

  function shiftWeek(days: number) {
    const d = new Date(`${selectedDate}T00:00:00`);
    d.setDate(d.getDate() + days);
    setSelectedDate(d.toISOString().slice(0, 10));
  }

  const dayTitle = useMemo(() => {
    if (selectedDate === today()) return 'Aujourd’hui';
    const d = new Date(`${selectedDate}T00:00:00`);
    const label = d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
    return label.charAt(0).toUpperCase() + label.slice(1);
  }, [selectedDate]);

  // "Mange la grenouille" (Eat the Frog) : parmi les tâches non finies, celle
  // qui angoisse le plus — on la met en avant plutôt que de laisser
  // l'utilisateur la repousser silencieusement toute la journée.
  const grenouille = useMemo(() => {
    const candidates = tasks.filter((t) => t.statut !== 'fait' && (t.niveau_dread ?? 0) >= 4);
    if (candidates.length === 0) return null;
    return candidates.sort((a, b) => (b.niveau_dread ?? 0) - (a.niveau_dread ?? 0))[0];
  }, [tasks]);

  // Heure de fin prévisible façon Sunsama : simple somme des estimations
  // restantes ajoutée à maintenant, pour visualiser la charge réelle du
  // reste de la journée sans avoir à faire le calcul soi-même.
  const heureFinPrevue = useMemo(() => {
    const restantes = tasks.filter((t) => t.statut !== 'fait' && t.estimation_minutes);
    if (restantes.length === 0) return null;
    const totalMinutes = restantes.reduce((sum, t) => sum + (t.estimation_minutes ?? 0), 0);
    const fin = new Date(Date.now() + totalMinutes * 60 * 1000);
    return fin.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }, [tasks]);

  // Batterie mentale : les tâches ne coûtent pas toutes la même chose
  // indépendamment de leur durée — un appel administratif de 5 min peut
  // coûter bien plus qu'une heure de rangement. Budget arbitraire mais
  // cohérent (10 points/jour) juste pour donner un signal relatif, pas une
  // mesure clinique.
  const COUT_POINTS: Record<'faible' | 'moyen' | 'eleve', number> = { faible: 1, moyen: 2, eleve: 3 };
  const BUDGET_ENERGIE_JOUR = 10;
  const batterieRestante = useMemo(() => {
    const utilisee = tasks
      .filter((t) => t.statut === 'fait' && t.cout_energie)
      .reduce((sum, t) => sum + COUT_POINTS[t.cout_energie!], 0);
    return Math.max(0, Math.round(100 - (utilisee / BUDGET_ENERGIE_JOUR) * 100));
  }, [tasks]);

  // Nudge premium au bon moment : proposer l'abonnement pendant une lancée
  // (streak qui passe un palier), pas quand on vient de bloquer quelque
  // chose. Non-abonné uniquement (couvre gratuit ET essai en cours, pour
  // convertir avant sa fin) — jamais pour un abonnement déjà actif.
  const STREAK_MILESTONES = [3, 7, 14, 30, 60, 100];
  const streakNudge = useMemo(() => {
    if (statut === 'actif' || nudgeDismissed) return null;
    if (streakDays == null || !STREAK_MILESTONES.includes(streakDays)) return null;
    return streakDays;
  }, [statut, streakDays, nudgeDismissed]);

  async function setDread(taskId: string, niveau: number) {
    await supabase.from('tasks').update({ niveau_dread: niveau }).eq('id', taskId);
    loadTasks();
  }

  async function setTaskMoment(taskId: string, moment: MomentJournee) {
    await supabase.from('tasks').update({ moment_journee: moment }).eq('id', taskId);
    loadTasks();
  }

  // Personnalisation manuelle icône/couleur (façon Tiimo "3000+ couleurs et
  // icônes") : tap sur la bulle d'icône d'une tâche ouvre un sélecteur, plutôt
  // que d'ajouter un nouveau bouton dans un en-tête déjà chargé.
  async function setTaskIcon(taskId: string, emoji: string, color: string) {
    await supabase.from('tasks').update({ icone_manuelle: emoji, couleur_manuelle: color }).eq('id', taskId);
    setIconPickerTaskId(null);
    loadTasks();
  }

  async function resetTaskIcon(taskId: string) {
    await supabase.from('tasks').update({ icone_manuelle: null, couleur_manuelle: null }).eq('id', taskId);
    setIconPickerTaskId(null);
    loadTasks();
  }

  // Priorité (urgence/importance) — distincte du niveau d'angoisse
  // (difficulté émotionnelle). Un tap fait défiler : rien → haute → moyenne
  // → basse → rien, pas besoin d'ouvrir un sélecteur pour trois options.
  async function cyclePriorite(task: Task) {
    const currentIndex = PRIORITE_CYCLE.indexOf(task.niveau_priorite);
    const next = PRIORITE_CYCLE[(currentIndex + 1) % PRIORITE_CYCLE.length];
    await supabase.from('tasks').update({ niveau_priorite: next }).eq('id', task.id);
    loadTasks();
  }

  const COUT_ENERGIE_CYCLE: (Task['cout_energie'])[] = [null, 'faible', 'moyen', 'eleve'];
  async function cycleCoutEnergie(task: Task) {
    const currentIndex = COUT_ENERGIE_CYCLE.indexOf(task.cout_energie);
    const next = COUT_ENERGIE_CYCLE[(currentIndex + 1) % COUT_ENERGIE_CYCLE.length];
    await supabase.from('tasks').update({ cout_energie: next }).eq('id', task.id);
    loadTasks();
  }

  // "Je suis en retard" (façon le co-planner Tiimo qui replanifie sur
  // commande) : décale d'un coup toutes les tâches restantes du jour qui ont
  // une heure fixée, sans avoir à les modifier une par une.
  async function delayRemainingTasks(minutes: number) {
    const concerned = tasks.filter((t) => t.statut !== 'fait' && t.heure_debut);
    await Promise.all(
      concerned.map((t) => {
        const [h, m] = t.heure_debut!.split(':').map(Number);
        const d = new Date();
        d.setHours(h, m + minutes, 0, 0);
        const newHeure = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:00`;
        return supabase.from('tasks').update({ heure_debut: newHeure }).eq('id', t.id);
      })
    );
    setRetardPickerVisible(false);
    loadTasks();
  }

  // Assistant conversationnel de planning (façon le chat IA de Tiimo qui
  // exécute des commandes) : l'IA classe le message dans une action fixe et
  // déterministe, c'est le client qui exécute — jamais l'IA qui écrit
  // directement en base, pour rester prévisible.
  async function submitAssistantMessage() {
    const texte = assistantInput.trim();
    if (!texte || !session) return;
    setAssistantMessages((prev) => [...prev, { role: 'user', text: texte }]);
    setAssistantInput('');
    setAssistantLoading(true);
    try {
      const taches = tasks
        .filter((t) => t.statut !== 'fait')
        .map((t) => ({
          id: t.id,
          titre: t.titre,
          heure_debut: t.heure_debut,
          niveau_priorite: t.niveau_priorite,
          niveau_dread: t.niveau_dread,
          statut: t.statut,
        }));
      const result = await interpretScheduleCommand(session.user.id, texte, taches);
      setAssistantMessages((prev) => [...prev, { role: 'assistant', text: result.message }]);
      await markAiUsage();

      if (result.action === 'decaler_tout') {
        await delayRemainingTasks(result.minutes ?? 10);
      } else if (result.action === 'reporter_tache' && result.tache_id) {
        await reportToTomorrow(result.tache_id);
      } else if (result.action === 'prioriser' && result.tache_id && result.niveau_priorite) {
        await supabase.from('tasks').update({ niveau_priorite: result.niveau_priorite }).eq('id', result.tache_id);
        loadTasks();
      }
    } catch {
      setAssistantMessages((prev) => [
        ...prev,
        { role: 'assistant', text: 'Je n’ai pas réussi à traiter ça pour le moment — réessaie dans un instant.' },
      ]);
    } finally {
      setAssistantLoading(false);
    }
  }

  const MIN_SAMPLE = 3;
  const LOW_COMPLETION_THRESHOLD = 0.5;

  // Suggestion du coach proactif : le moment choisi a un faible taux de
  // réussite historique sur des tâches aussi angoissantes, et il existe un
  // autre moment avec un net meilleur taux — sinon, pas la peine d'avertir.
  function getMomentWarning(task: Task) {
    if (!momentStats || (task.niveau_dread ?? 0) < 4) return null;
    const current = momentStats[task.moment_journee];
    if (!current || current.total < MIN_SAMPLE) return null;
    const currentRate = current.completed / current.total;
    if (currentRate >= LOW_COMPLETION_THRESHOLD) return null;

    const better = MOMENT_ORDER.filter((m) => m !== task.moment_journee)
      .map((m) => ({ moment: m, stats: momentStats[m] }))
      .filter((s) => s.stats.total >= MIN_SAMPLE && s.stats.completed / s.stats.total > currentRate + 0.2)
      .sort((a, b) => b.stats.completed / b.stats.total - a.stats.completed / a.stats.total)[0];

    if (!better) return null;
    return { currentRate, better };
  }

  // Réorganisation manuelle dans une section : la plainte la plus citée sur
  // Tiimo dans les avis App Store est de ne pas pouvoir déplacer une tâche
  // une fois ajoutée. On renumérote toute la section pour rester cohérent
  // même si plusieurs tâches partagent le même ordre au départ.
  async function moveTask(sectionData: Task[], taskId: string, direction: -1 | 1) {
    const index = sectionData.findIndex((t) => t.id === taskId);
    const swapIndex = index + direction;
    if (index === -1 || swapIndex < 0 || swapIndex >= sectionData.length) return;

    const reordered = [...sectionData];
    [reordered[index], reordered[swapIndex]] = [reordered[swapIndex], reordered[index]];

    await Promise.all(reordered.map((t, i) => supabase.from('tasks').update({ ordre: i }).eq('id', t.id)));
    loadTasks();
  }

  function startFocusOn(task: Task) {
    router.push(`/focus?tache=${encodeURIComponent(task.titre)}&tacheId=${task.id}`);
  }

  // Verrouillage doux (jamais bloquant) : avertir avant de s'engager sur une
  // tâche coûteuse en énergie quand la batterie du jour est basse, sans
  // jamais empêcher de le faire quand même.
  function lancerFocusAvecCheck(task: Task) {
    if (task.cout_energie === 'eleve' && batterieRestante < 25) {
      Alert.alert(
        'Batterie mentale basse',
        `Il te reste environ ${batterieRestante}% — cette tâche coûte cher en énergie. Tu veux t'y lancer quand même ?`,
        [
          { text: 'Plus tard', style: 'cancel' },
          { text: 'Je me lance', onPress: () => startFocusOn(task) },
        ]
      );
      return;
    }
    startFocusOn(task);
  }

  // Mode focus : garde l'emoji (utile pour reconnaître une tâche d'un coup
  // d'œil) mais neutralise la bulle colorée — une liste de tâches, c'est
  // potentiellement une dizaine de teintes pastel différentes affichées en
  // même temps, exactement le genre de touche décorative répétée que le
  // mode focus retire.
  function iconColorFor(task: Task) {
    return focusMode ? colors.surfaceAlt : resolveTaskIcon(task).color;
  }

  async function submitBraindump() {
    if (!braindumpText.trim() || !session) return;
    setBraindumpLoading(true);
    try {
      const count =
        braindumpScope === 'semaine'
          ? await planWeekFromBraindump(session.user.id, braindumpText.trim())
          : await planFromBraindump(session.user.id, braindumpText.trim());
      setBraindumpText('');
      setBraindumpVisible(false);
      await loadTasks();
      await markAiUsage();
      const lieu = braindumpScope === 'semaine' ? 'ta semaine' : 'ta journée';
      Alert.alert('Planning généré', `${count} tâche${count > 1 ? 's' : ''} ajoutée${count > 1 ? 's' : ''} à ${lieu}.`);
    } catch {
      Alert.alert('L’IA n’a pas pu générer ton planning', 'Réessaie dans un instant, ou ajoute tes tâches une par une.');
    } finally {
      setBraindumpLoading(false);
    }
  }

  async function saveEstimation(taskId: string) {
    const value = parseInt(estimationInput[taskId] ?? '', 10);
    if (!value || Number.isNaN(value)) return;
    await supabase.from('tasks').update({ estimation_minutes: value, statut: 'en_cours' }).eq('id', taskId);
    loadTasks();
  }

  // "Taxe TDAH" : le temps réellement nécessaire est presque toujours sous-
  // estimé. Suggestion visible et tapable plutôt qu'une multiplication
  // silencieuse — écraser la saisie fausserait aussi la calibration
  // estimé/réel déjà en place ailleurs dans l'app.
  function estimationSuggeree(taskId: string): number | null {
    const brut = parseInt(estimationInput[taskId] ?? '', 10);
    if (!brut || Number.isNaN(brut)) return null;
    const suggeree = Math.round((brut * 1.4) / 5) * 5;
    return suggeree > brut ? suggeree : null;
  }

  function appliquerEstimationSuggeree(taskId: string) {
    const suggeree = estimationSuggeree(taskId);
    if (suggeree) setEstimationInput((prev) => ({ ...prev, [taskId]: String(suggeree) }));
  }

  async function decompose(taskId: string, titre: string, niveauDread: number | null) {
    setDecomposingId(taskId);
    try {
      const granularite = granulariteByTask[taskId] ?? 2;
      const sousTaches = await breakdownTask(titre, profile?.preference_ton ?? 'doux', granularite, niveauDread ?? undefined);
      const rows = sousTaches.map((titre, ordre) => ({ task_id: taskId, titre, ordre }));
      await supabase.from('subtasks').insert(rows);
      await loadTasks();
    } catch {
      Alert.alert('L’IA n’a pas pu découper la tâche', 'Réessaie dans un instant.');
    } finally {
      setDecomposingId(null);
    }
  }

  // "Too Hard Right Now" (Focus One) : reporter une tâche au lendemain du
  // jour où elle est prévue, sans aucune trace de culpabilité — pas de badge
  // "en retard", pas de compteur d'échecs, juste un déplacement de date.
  // Répond directement à la plainte la plus citée dans les avis
  // Tiimo/Sunsama : aucune app ADHD ne gère bien le report.
  async function reportToTomorrow(taskId: string) {
    const base = new Date(selectedDate);
    base.setDate(base.getDate() + 1);
    await supabase
      .from('tasks')
      .update({ date_prevue: base.toISOString().slice(0, 10) })
      .eq('id', taskId);
    await cancelTaskReminder(taskId);
    loadTasks();
  }

  // Heure de début manuelle (le Vide-tête en pose déjà automatiquement, mais
  // une tâche ajoutée à la main n'en a pas) — nécessaire pour que les
  // rappels et la vue frise aient quelque chose à afficher.
  async function setTaskTime(taskId: string, hhmm: string) {
    if (!/^([01]\d|2[0-3]):([0-5]\d)$/.test(hhmm)) {
      Alert.alert('Format invalide', 'Utilise le format HH:MM, ex : 14:30.');
      return;
    }
    await supabase.from('tasks').update({ heure_debut: `${hhmm}:00` }).eq('id', taskId);
    loadTasks();
  }

  // Plan "si...alors..." (implementation intention) : preuve scientifique
  // solide pour contourner le déficit exécutif — un déclencheur
  // environnemental prend le relais plutôt que de compter sur la volonté.
  async function saveSiAlors(taskId: string) {
    const value = (siAlorsInput[taskId] ?? '').trim();
    await supabase.from('tasks').update({ si_alors: value || null }).eq('id', taskId);
    setSiAlorsEditId(null);
    loadTasks();
  }

  async function addToCalendar(task: Task) {
    try {
      const ok = await syncTaskToCalendar({
        id: task.id,
        titre: task.titre,
        date_prevue: selectedDate,
        estimation_minutes: task.estimation_minutes,
      });
      if (!ok) {
        Alert.alert('Permission refusée', 'Autorise l’accès au calendrier dans les réglages de ton téléphone pour utiliser cette fonction.');
        return;
      }
      Alert.alert('Ajouté', 'La tâche est maintenant dans ton calendrier.');
    } catch {
      Alert.alert('Erreur', 'Impossible d’ajouter cette tâche au calendrier pour le moment.');
    }
  }

  async function toggleSubtask(subtask: Subtask) {
    const nowFait = !subtask.fait;
    await supabase.from('subtasks').update({ fait: nowFait }).eq('id', subtask.id);
    if (nowFait && session) {
      await bumpStreak(session.user.id);
      celebrate(profile?.preference_gamification ?? 'discrete');
    }
    loadTasks();
  }

  async function completeTask(task: Task, tempsReel?: number) {
    await supabase
      .from('tasks')
      .update({ statut: 'fait', temps_reel_minutes: tempsReel ?? task.temps_reel_minutes })
      .eq('id', task.id);
    await cancelTaskReminder(task.id);
    if (session) {
      await bumpStreak(session.user.id);
      await maybeUnlockFirstTaskBadge(session.user.id);
      celebrate(profile?.preference_gamification ?? 'discrete');
    }
    loadTasks();
  }

  function markTaskDone(task: Task) {
    if (task.statut === 'fait') return;

    if (task.estimation_minutes && !task.temps_reel_minutes && Platform.OS === 'ios' && Alert.prompt) {
      Alert.prompt(
        'Combien de temps ça t’a pris ?',
        `Tu avais estimé ${task.estimation_minutes} min.`,
        (value) => {
          const minutes = parseInt(value ?? '', 10);
          completeTask(task, Number.isNaN(minutes) ? undefined : minutes);
        },
        'plain-text',
        String(task.estimation_minutes)
      );
      return;
    }
    completeTask(task);
  }

  // IA gratuite mais LIMITÉE (façon Tiimo), jamais totalement bloquée — le
  // blocage complet d'une fonctionnalité déjà essayée est le vrai
  // déclencheur de désinstalls/avis 1 étoile. Usage illimité en premium.
  function requireAi(label: string, action: () => void) {
    if (aiQuotaOk) {
      action();
      return;
    }
    Alert.alert(
      'Limite gratuite atteinte',
      `Tu as utilisé tes ${aiLimit} essais gratuits de ${label} ce mois-ci — l’app reste gratuite pour le planning, le focus et les check-ins du quotidien. Passe à l’abonnement pour un usage illimité.`,
      [
        { text: 'Plus tard', style: 'cancel' },
        { text: 'Voir les offres', onPress: () => router.push('/paiement') },
      ]
    );
  }

  // Roulette des tâches : face à une longue liste, le choix lui-même devient
  // un obstacle (fatigue décisionnelle) — supprimer la décision plutôt que
  // d'aider à la prendre.
  function choisirPourMoi() {
    const candidats = tasks.filter((t) => t.statut !== 'fait');
    if (candidats.length === 0) {
      Alert.alert('Rien à choisir', 'Toutes tes tâches du jour sont déjà faites 🎉');
      return;
    }
    const pick = candidats[Math.floor(Math.random() * candidats.length)];
    Alert.alert('🎲 On y va', `"${pick.titre}"`, [
      { text: 'Une autre', onPress: () => choisirPourMoi() },
      { text: 'Plus tard', style: 'cancel' },
      { text: 'Lancer le focus', onPress: () => startFocusOn(pick) },
    ]);
  }

  // "Amnistie générale" : les tâches en retard deviennent vite une source de
  // honte qui pousse à fuir l'app plutôt qu'à rattraper le retard. Un geste
  // qui remet tout à aujourd'hui, sans compteur d'échec ni notification
  // culpabilisante — page blanche assumée, cohérent avec le report non-
  // punitif déjà en place tâche par tâche.
  async function confirmerAmnistie() {
    if (!session) return;
    const { data, error } = await supabase
      .from('tasks')
      .select('id')
      .eq('user_id', session.user.id)
      .lt('date_prevue', today())
      .neq('statut', 'fait');
    if (error) return;
    if (!data || data.length === 0) {
      Alert.alert('Rien à amnistier', 'Aucune tâche en retard en ce moment.');
      return;
    }
    Alert.alert(
      'Amnistie générale',
      `${data.length} tâche${data.length > 1 ? 's' : ''} en retard reviendra${data.length > 1 ? 'ont' : ''} à aujourd’hui — pas de compteur, pas de jugement.`,
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Je fais table rase',
          onPress: async () => {
            const ids = data.map((t) => t.id);
            await supabase.from('tasks').update({ date_prevue: today() }).in('id', ids);
            await Promise.all(ids.map((id) => cancelTaskReminder(id)));
            await loadTasks();
            Alert.alert('Page blanche', 'On repart de là, sans arriéré.');
          },
        },
      ]
    );
  }

  // Mode Crash : quand le cerveau "s'éteint" (surcharge sensorielle ou
  // émotionnelle), choisir quoi faire est lui-même un obstacle. On coupe
  // court plutôt que de laisser la liste du jour peser : les rappels
  // s'arrêtent, tout est reporté à demain sauf la tâche la moins angoissante,
  // même celle-là restant facultative.
  async function activerModeCrash() {
    if (!session) return;
    const restantes = tasks.filter((t) => t.statut !== 'fait');
    await Promise.all(restantes.map((t) => cancelTaskReminder(t.id)));
    const aGarder = restantes.length > 0
      ? [...restantes].sort((a, b) => (a.niveau_dread ?? 0) - (b.niveau_dread ?? 0))[0]
      : null;
    const aReporter = restantes.filter((t) => t.id !== aGarder?.id);
    if (aReporter.length > 0) {
      const demain = new Date(selectedDate);
      demain.setDate(demain.getDate() + 1);
      await supabase
        .from('tasks')
        .update({ date_prevue: demain.toISOString().slice(0, 10) })
        .in('id', aReporter.map((t) => t.id));
    }
    setModeCrashVisible(false);
    await loadTasks();
    Alert.alert(
      'Mode Crash activé',
      aGarder
        ? `Tout est reporté à demain sauf "${aGarder.titre}" — et même celle-là, seulement si tu en as la force.`
        : 'Tout est reporté à demain. Repose-toi.'
    );
  }

  // Générateur de réponses aux messages fantômes : un message resté sans
  // réponse trop longtemps par évitement/anxiété devient une source
  // d'angoisse qui s'auto-alimente. L'IA propose un brouillon court, jamais
  // envoyé automatiquement — l'utilisateur reste seul maître de l'envoi.
  async function submitGhostReply() {
    if (!ghostReplyContext.trim() || !session) return;
    setGhostReplyLoading(true);
    try {
      const reply = await generateGhostReply(session.user.id, ghostReplyContext.trim());
      setGhostReplyResult(reply);
      await markAiUsage();
    } catch {
      Alert.alert('L’IA n’a pas pu générer de réponse', 'Réessaie dans un instant.');
    } finally {
      setGhostReplyLoading(false);
    }
  }

  async function copierReponseFantome() {
    await Clipboard.setStringAsync(ghostReplyResult);
    Alert.alert('Copié', 'Le brouillon est dans ton presse-papiers.');
  }

  // Menu "Outils" : regroupe les actions secondaires derrière un seul bouton
  // plutôt que d'aligner 6 chips en permanence dans l'en-tête — la ligne de
  // boutons avait fini par déborder sur deux lignes au fil des ajouts.
  const TOOLS: { icon: keyof typeof Ionicons.glyphMap; label: string; onPress: () => void; premium?: boolean; quota?: boolean }[] = [
    { icon: 'sparkles-outline', label: 'Assistant', onPress: () => requireAi('l’assistant conversationnel', () => setAssistantVisible(true)), quota: true },
    { icon: 'chatbox-ellipses-outline', label: 'Réponse à un message', onPress: () => requireAi('le générateur de réponses', () => setGhostReplyVisible(true)), quota: true },
    { icon: 'shuffle-outline', label: 'Choisis pour moi', onPress: choisirPourMoi },
    { icon: 'albums-outline', label: 'Backlog', onPress: () => router.push('/backlog') },
    { icon: 'repeat-outline', label: 'Routines', onPress: () => router.push('/routines') },
    { icon: 'moon-outline', label: 'Fin de journée', onPress: () => router.push('/rituel-fin-journee') },
    { icon: 'leaf-outline', label: 'Respirer', onPress: () => router.push('/respiration') },
    { icon: 'bed-outline', label: 'Sommeil', onPress: () => gate('Le suivi du sommeil', () => router.push('/sommeil')), premium: true },
    { icon: 'refresh-circle-outline', label: 'Amnistie générale', onPress: confirmerAmnistie },
    { icon: 'alert-circle-outline', label: 'Mode Crash', onPress: () => setModeCrashVisible(true) },
  ];

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  return (
    <KeyboardAvoidingView style={styles.container} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={styles.titleRow}>
        <Text style={styles.title}>{dayTitle}</Text>
        {streakDays != null && streakDays > 0 && (
          <View style={styles.streakBadge}>
            <Text style={styles.streakBadgeText}>🔥 {streakDays}</Text>
          </View>
        )}
        {tasks.some((t) => t.cout_energie) && (
          <View style={styles.energyGauge}>
            <Text style={styles.energyGaugeText}>{batterieRestante}%</Text>
            <View style={styles.energyGaugeTrack}>
              <LinearGradient
                colors={gradients.energy}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={[styles.energyGaugeFill, { width: `${batterieRestante}%` }]}
              />
            </View>
          </View>
        )}
      </View>

      <View style={styles.weekRow}>
        <Pressable hitSlop={13} onPress={() => shiftWeek(-7)}>
          <Ionicons name="chevron-back" size={18} color={colors.textMuted} />
        </Pressable>
        {weekDays.map((d) => {
          const dateObj = new Date(`${d}T00:00:00`);
          const isSelected = d === selectedDate;
          const isToday = d === today();
          return (
            <Pressable key={d} style={[styles.dayChip, isSelected && styles.dayChipActive]} onPress={() => setSelectedDate(d)}>
              <Text style={[styles.dayChipLetter, isSelected && styles.dayChipTextActive]}>{WEEKDAY_LETTERS[dateObj.getDay() === 0 ? 6 : dateObj.getDay() - 1]}</Text>
              <Text style={[styles.dayChipNumber, isSelected && styles.dayChipTextActive]}>{dateObj.getDate()}</Text>
              {isToday && !isSelected && <View style={styles.dayChipDot} />}
            </Pressable>
          );
        })}
        <Pressable hitSlop={13} onPress={() => shiftWeek(7)}>
          <Ionicons name="chevron-forward" size={18} color={colors.textMuted} />
        </Pressable>
      </View>

      <View style={styles.headerButtons}>
        <Pressable style={styles.braindumpButton} onPress={() => requireAi('Vide-tête', () => setBraindumpVisible(true))}>
          <Ionicons name="chatbubble-ellipses-outline" size={16} color={colors.primary} />
          <Text style={styles.braindumpButtonText}>Vide-tête</Text>
          {!isPremium && <Text style={styles.aiQuotaBadge}>{aiRemaining}</Text>}
        </Pressable>
        <Pressable
          style={styles.braindumpButton}
          onPress={() => setVueMode((v) => (v === 'liste' ? 'timeline' : 'liste'))}
        >
          <Ionicons name={vueMode === 'liste' ? 'time-outline' : 'list-outline'} size={16} color={colors.primary} />
          <Text style={styles.braindumpButtonText}>{vueMode === 'liste' ? 'Frise' : 'Liste'}</Text>
        </Pressable>
        <Pressable style={styles.braindumpButton} onPress={() => setToolsMenuVisible(true)}>
          <Ionicons name="ellipsis-horizontal" size={16} color={colors.primary} />
          <Text style={styles.braindumpButtonText}>Outils</Text>
        </Pressable>
      </View>
      {calibrationInsight && <Text style={styles.insight}>💡 {calibrationInsight}</Text>}
      {heureFinPrevue && (
        <View style={styles.insightRow}>
          <Text style={[styles.insight, { flex: 1, marginBottom: 0 }]}>🕓 À ce rythme, tu termines vers {heureFinPrevue}.</Text>
          <Pressable style={styles.retardButton} onPress={() => setRetardPickerVisible((v) => !v)}>
            <Text style={styles.retardButtonText}>En retard ?</Text>
          </Pressable>
        </View>
      )}
      {retardPickerVisible && (
        <View style={styles.retardPicker}>
          {[5, 10, 15, 30].map((m) => (
            <Pressable key={m} style={styles.retardChip} onPress={() => delayRemainingTasks(m)}>
              <Text style={styles.retardChipText}>+{m} min</Text>
            </Pressable>
          ))}
        </View>
      )}
      {grenouille && (
        <Pressable style={styles.grenouilleBanner} onPress={() => startFocusOn(grenouille)}>
          <Text style={styles.grenouilleText}>🐸 Commence par ta grenouille : "{grenouille.titre}"</Text>
          <Text style={styles.grenouilleAction}>Lancer le focus dessus →</Text>
        </Pressable>
      )}

      {streakNudge != null && (
        <View style={styles.nudgeBanner}>
          <Text style={styles.nudgeText}>🔥 {streakNudge} jours d’affilée — tu es sur une vraie lancée.</Text>
          <View style={styles.nudgeActions}>
            <Pressable onPress={() => setNudgeDismissed(true)}>
              <Text style={styles.nudgeDismiss}>Plus tard</Text>
            </Pressable>
            <Pressable
              style={styles.nudgeCta}
              onPress={() => {
                setNudgeDismissed(true);
                router.push('/paiement');
              }}
            >
              <Text style={styles.nudgeCtaText}>✨ Passer à l’illimité</Text>
            </Pressable>
          </View>
        </View>
      )}

      {vueMode === 'timeline' ? (
        tasks.length === 0 ? (
          <Text style={styles.empty}>Rien de prévu pour l’instant — ajoute une première tâche en bas, ou décris ta journée avec "Vide-tête".</Text>
        ) : (
          <TimelineView
            tasks={tasks}
            onToggleDone={(t) => {
              const full = tasks.find((x) => x.id === t.id);
              if (full) markTaskDone(full);
            }}
            onFocus={(t) => {
              const full = tasks.find((x) => x.id === t.id);
              if (full) startFocusOn(full);
            }}
          />
        )
      ) : (
      <SectionList
        sections={sections}
        keyExtractor={(t) => t.id}
        stickySectionHeadersEnabled={false}
        contentContainerStyle={{ paddingBottom: spacing.xl }}
        ListEmptyComponent={
          <Text style={styles.empty}>Rien de prévu pour l’instant — ajoute une première tâche en bas, ou décris ta journée avec "Vide-tête".</Text>
        }
        renderSectionHeader={({ section }) => (
          <Pressable style={styles.sectionHeaderRow} onPress={() => toggleSection(section.moment)}>
            <Text style={styles.sectionHeader}>
              {section.title} <Text style={styles.sectionCount}>({section.count})</Text>
            </Text>
            <Ionicons
              name={collapsedSections[section.moment] ? 'chevron-down' : 'chevron-up'}
              size={16}
              color={colors.textMuted}
            />
          </Pressable>
        )}
        renderItem={({ item, index, section }) => {
          const momentWarning = getMomentWarning(item);
          return (
          <View style={[styles.taskCard, item.statut === 'fait' && styles.taskCardDone]}>
            <View style={styles.reorderColumn}>
              <Pressable hitSlop={8} disabled={index === 0} onPress={() => moveTask(section.data, item.id, -1)}>
                <Ionicons name="chevron-up" size={16} color={index === 0 ? colors.border : colors.textMuted} />
              </Pressable>
              <Pressable hitSlop={8} disabled={index === section.data.length - 1} onPress={() => moveTask(section.data, item.id, 1)}>
                <Ionicons name="chevron-down" size={16} color={index === section.data.length - 1 ? colors.border : colors.textMuted} />
              </Pressable>
            </View>
            <View style={styles.taskBody}>
            <View style={styles.taskHeader}>
              {item.statut !== 'fait' && (
                <Pressable hitSlop={8} onPress={() => cyclePriorite(item)}>
                  <Ionicons
                    name={item.niveau_priorite ? 'flag' : 'flag-outline'}
                    size={16}
                    color={item.niveau_priorite ? PRIORITE_COLOR[item.niveau_priorite] : colors.border}
                  />
                </Pressable>
              )}
              {item.statut !== 'fait' && (
                <Pressable hitSlop={8} onPress={() => cycleCoutEnergie(item)}>
                  <Ionicons
                    name={item.cout_energie ? 'flash' : 'flash-outline'}
                    size={16}
                    color={
                      item.cout_energie === 'eleve'
                        ? colors.danger
                        : item.cout_energie === 'moyen'
                        ? colors.warning
                        : item.cout_energie === 'faible'
                        ? colors.success
                        : colors.border
                    }
                  />
                </Pressable>
              )}
              <Pressable
                hitSlop={4}
                onPress={() =>
                  gate('La personnalisation d’icône', () => {
                    setPickerColor(resolveTaskIcon(item).color);
                    setIconPickerTaskId(item.id);
                  })
                }
              >
                <View style={[styles.taskIconBubble, { backgroundColor: iconColorFor(item) }]}>
                  <Text style={styles.taskIconEmoji}>{resolveTaskIcon(item).emoji}</Text>
                  {item.statut === 'fait' && (
                    <View style={styles.taskIconCheckBadge}>
                      <Ionicons name="checkmark-circle" size={16} color={colors.success} />
                    </View>
                  )}
                </View>
              </Pressable>
              <Pressable style={styles.taskHeaderMain} onPress={() => markTaskDone(item)}>
                <Text style={[styles.taskTitle, item.statut === 'fait' && styles.taskTitleDone]}>{item.titre}</Text>
              </Pressable>
              {item.statut !== 'fait' && (
                <Pressable hitSlop={8} onPress={() => lancerFocusAvecCheck(item)}>
                  <Ionicons name="play-circle-outline" size={20} color={colors.textMuted} />
                </Pressable>
              )}
              <Pressable hitSlop={13} style={styles.overflowButton} onPress={() => setOverflowTask(item)}>
                <Ionicons name="ellipsis-vertical" size={18} color={colors.textMuted} />
              </Pressable>
            </View>

            {item.estimation_minutes && (
              <Text style={styles.caption}>
                Estimé {item.estimation_minutes} min
                {item.temps_reel_minutes ? ` · réel ${item.temps_reel_minutes} min` : ''}
              </Text>
            )}

            {item.statut !== 'fait' && (
              <View style={styles.dreadRow}>
                <Text style={styles.dreadLabel}>Angoisse</Text>
                {([1, 2, 3, 4, 5] as const).map((n) => (
                  <Pressable key={n} hitSlop={4} onPress={() => setDread(item.id, n)}>
                    <Ionicons
                      name={(item.niveau_dread ?? 0) >= n ? 'flame' : 'flame-outline'}
                      size={16}
                      color={(item.niveau_dread ?? 0) >= n ? colors.warning : colors.textMuted}
                    />
                  </Pressable>
                ))}
              </View>
            )}

            {item.statut !== 'fait' && momentWarning && (
              <View style={styles.coachWarning}>
                <Text style={styles.coachWarningText}>
                  ⚠️ Tu termines rarement tes tâches difficiles {MOMENT_LABELS[item.moment_journee].toLowerCase()} (
                  {Math.round(momentWarning.currentRate * 100)}%) — le {MOMENT_LABELS[momentWarning.better.moment].toLowerCase()} marche mieux pour toi (
                  {Math.round((momentWarning.better.stats.completed / momentWarning.better.stats.total) * 100)}%).
                </Text>
                <Pressable
                  style={styles.coachWarningButton}
                  onPress={() => setTaskMoment(item.id, momentWarning.better.moment)}
                >
                  <Text style={styles.coachWarningButtonText}>Passer {MOMENT_LABELS[momentWarning.better.moment].toLowerCase()}</Text>
                </Pressable>
              </View>
            )}

            {item.statut !== 'fait' && siAlorsEditId === item.id ? (
              <View style={styles.inputPairRow}>
                <TextInput
                  style={[styles.estimationInput, { flex: 1 }]}
                  placeholder="Si je bloque, alors je..."
                  placeholderTextColor={colors.textMuted}
                  value={siAlorsInput[item.id] ?? item.si_alors ?? ''}
                  onChangeText={(v) => setSiAlorsInput((prev) => ({ ...prev, [item.id]: v }))}
                  onSubmitEditing={() => saveSiAlors(item.id)}
                  autoFocus
                />
                <Pressable style={styles.siAlorsSaveButton} onPress={() => saveSiAlors(item.id)}>
                  <Ionicons name="checkmark" size={18} color="#fff" />
                </Pressable>
              </View>
            ) : item.statut !== 'fait' && item.si_alors ? (
              <Pressable
                style={styles.siAlorsChip}
                onPress={() => {
                  setSiAlorsInput((prev) => ({ ...prev, [item.id]: item.si_alors ?? '' }));
                  setSiAlorsEditId(item.id);
                }}
              >
                <Text style={styles.siAlorsChipText}>🔗 {item.si_alors}</Text>
              </Pressable>
            ) : item.statut !== 'fait' ? (
              <Pressable onPress={() => setSiAlorsEditId(item.id)}>
                <Text style={styles.siAlorsAddLink}>+ Si... alors... (plan anti-blocage)</Text>
              </Pressable>
            ) : null}

            {item.statut !== 'fait' && (!item.estimation_minutes || !item.heure_debut) && (
              <View style={[styles.estimationRow, styles.inputPairRow]}>
                {!item.heure_debut && (
                  <TextInput
                    style={[styles.estimationInput, { flex: 1 }]}
                    placeholder="14:30"
                    placeholderTextColor={colors.textMuted}
                    value={timeInput[item.id] ?? ''}
                    onChangeText={(v) => setTimeInput((prev) => ({ ...prev, [item.id]: v }))}
                    onSubmitEditing={() => setTaskTime(item.id, timeInput[item.id] ?? '')}
                  />
                )}
                {!item.estimation_minutes && (
                  <TextInput
                    style={[styles.estimationInput, { flex: 1 }]}
                    placeholder="Durée (min)"
                    placeholderTextColor={colors.textMuted}
                    keyboardType="number-pad"
                    value={estimationInput[item.id] ?? ''}
                    onChangeText={(v) => setEstimationInput((prev) => ({ ...prev, [item.id]: v }))}
                    onSubmitEditing={() => saveEstimation(item.id)}
                  />
                )}
              </View>
            )}

            {item.statut !== 'fait' && !item.estimation_minutes && estimationSuggeree(item.id) != null && (
              <Pressable onPress={() => appliquerEstimationSuggeree(item.id)}>
                <Text style={styles.taxeSuggestion}>💡 Prévois plutôt {estimationSuggeree(item.id)} min — marge de sécurité TDAH</Text>
              </Pressable>
            )}

            {item.subtasks?.length > 0 ? (
              item.subtasks
                .sort((a, b) => a.ordre - b.ordre)
                .map((s) => (
                  <Pressable key={s.id} style={styles.subtaskRow} onPress={() => toggleSubtask(s)}>
                    <Ionicons
                      name={s.fait ? 'checkbox' : 'square-outline'}
                      size={18}
                      color={s.fait ? colors.success : colors.textMuted}
                    />
                    <Text style={[styles.subtaskText, s.fait && styles.taskTitleDone]}>{s.titre}</Text>
                  </Pressable>
                ))
            ) : (
              <View>
                <View style={styles.granulariteRow}>
                  {([1, 2, 3] as const).map((g) => (
                    <Pressable
                      key={g}
                      style={[
                        styles.granulariteChip,
                        (granulariteByTask[item.id] ?? 2) === g && styles.granulariteChipActive,
                      ]}
                      onPress={() => setGranulariteByTask((prev) => ({ ...prev, [item.id]: g }))}
                    >
                      <Text
                        style={[
                          styles.granulariteText,
                          (granulariteByTask[item.id] ?? 2) === g && styles.granulariteTextActive,
                        ]}
                      >
                        {GRANULARITE_LABELS[g]}
                      </Text>
                    </Pressable>
                  ))}
                </View>
                <Pressable
                  style={styles.decomposeButton}
                  onPress={() => decompose(item.id, item.titre, item.niveau_dread)}
                  disabled={decomposingId === item.id}
                >
                  {decomposingId === item.id ? (
                    <ActivityIndicator size="small" color={colors.primary} />
                  ) : (
                    <>
                      <Ionicons name="sparkles-outline" size={16} color={colors.primary} />
                      <Text style={styles.decomposeText}>Découper avec l’IA</Text>
                    </>
                  )}
                </Pressable>
              </View>
            )}
            </View>
          </View>
          );
        }}
      />
      )}

      <InteroceptionCheckIn
        visible={checkInVisible}
        contexteDeclencheur="session_prolongee_planning"
        gamificationPref={profile?.preference_gamification ?? 'discrete'}
        onClose={() => setCheckInVisible(false)}
      />

      <Modal visible={braindumpVisible} transparent animationType="slide" onRequestClose={() => setBraindumpVisible(false)}>
        <View style={styles.braindumpBackdrop}>
          <View style={styles.braindumpCard}>
            <Text style={styles.braindumpTitle}>Vide-tête</Text>
            <Text style={styles.braindumpSubtitle}>
              {braindumpScope === 'semaine'
                ? 'Décris tout ce que t\'as à faire cette semaine, en vrac — l\'IA répartit intelligemment sur les 7 jours.'
                : 'Décris tout ce que t\'as à faire aujourd\'hui, en vrac, comme ça vient — l\'IA construit le planning pour toi.'}
            </Text>
            <View style={styles.braindumpScopeRow}>
              <Pressable
                style={[styles.braindumpScopeChip, braindumpScope === 'jour' && styles.braindumpScopeChipActive]}
                onPress={() => setBraindumpScope('jour')}
              >
                <Text style={[styles.braindumpScopeText, braindumpScope === 'jour' && styles.braindumpScopeTextActive]}>Aujourd'hui</Text>
              </Pressable>
              <Pressable
                style={[styles.braindumpScopeChip, braindumpScope === 'semaine' && styles.braindumpScopeChipActive]}
                onPress={() => setBraindumpScope('semaine')}
              >
                <Text style={[styles.braindumpScopeText, braindumpScope === 'semaine' && styles.braindumpScopeTextActive]}>Toute la semaine</Text>
              </Pressable>
            </View>
            <TextInput
              style={styles.braindumpInput}
              multiline
              placeholder={
                braindumpScope === 'semaine'
                  ? "Ex : lundi j'ai le dentiste à 10h, il faut que j'appelle le comptable cette semaine, sport mardi et jeudi, anniversaire de Léo samedi..."
                  : 'Ex : je dois appeler maman, prendre mon petit déjeuner, aller au travail et récupérer les enfants cet après-midi...'
              }
              placeholderTextColor={colors.textMuted}
              value={braindumpText}
              onChangeText={setBraindumpText}
              autoFocus
            />
            <View style={styles.braindumpActions}>
              <Pressable onPress={() => setBraindumpVisible(false)}>
                <Text style={styles.braindumpCancel}>Annuler</Text>
              </Pressable>
              <Pressable style={styles.braindumpSubmit} onPress={submitBraindump} disabled={braindumpLoading}>
                {braindumpLoading ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <Text style={styles.braindumpSubmitText}>Allez, c'est parti 🙌</Text>
                )}
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      <Modal
        visible={iconPickerTaskId != null}
        transparent
        animationType="slide"
        onRequestClose={() => setIconPickerTaskId(null)}
      >
        <View style={styles.braindumpBackdrop}>
          <View style={styles.braindumpCard}>
            <Text style={styles.braindumpTitle}>Icône & couleur</Text>
            <Text style={styles.braindumpSubtitle}>Choisis une couleur, puis une icône — ou laisse l'IA deviner automatiquement.</Text>
            <View style={styles.colorRow}>
              {COLOR_CHOICES.map((c) => (
                <Pressable
                  key={c}
                  style={[styles.colorSwatch, { backgroundColor: c }, pickerColor === c && styles.colorSwatchActive]}
                  onPress={() => setPickerColor(c)}
                />
              ))}
            </View>
            <View style={styles.iconGrid}>
              {ICON_CHOICES.map((emoji) => (
                <Pressable
                  key={emoji}
                  style={[styles.iconChoice, { backgroundColor: pickerColor }]}
                  onPress={() => iconPickerTaskId && setTaskIcon(iconPickerTaskId, emoji, pickerColor)}
                >
                  <Text style={styles.taskIconEmoji}>{emoji}</Text>
                </Pressable>
              ))}
            </View>
            <View style={styles.braindumpActions}>
              <Pressable onPress={() => iconPickerTaskId && resetTaskIcon(iconPickerTaskId)}>
                <Text style={styles.braindumpCancel}>Revenir à l'auto</Text>
              </Pressable>
              <Pressable onPress={() => setIconPickerTaskId(null)}>
                <Text style={styles.braindumpCancel}>Fermer</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      <Modal visible={toolsMenuVisible} transparent animationType="slide" onRequestClose={() => setToolsMenuVisible(false)}>
        <View style={styles.braindumpBackdrop}>
          <View style={styles.braindumpCard}>
            <Text style={styles.braindumpTitle}>Outils</Text>
            {TOOLS.map((tool) => (
              <Pressable
                key={tool.label}
                style={styles.toolRow}
                onPress={() => {
                  setToolsMenuVisible(false);
                  tool.onPress();
                }}
              >
                <Ionicons name={tool.icon} size={20} color={colors.primary} />
                <Text style={styles.toolRowText}>{tool.label}</Text>
                {tool.premium && !isPremium && (
                  <View style={styles.premiumChip}>
                    <Text style={styles.premiumChipText}>✨ Premium</Text>
                  </View>
                )}
                {tool.quota && !isPremium && (
                  <Text style={styles.toolQuotaBadge}>{aiRemaining}/{aiLimit}</Text>
                )}
              </Pressable>
            ))}
            <Pressable onPress={() => setToolsMenuVisible(false)} style={{ marginTop: spacing.sm }}>
              <Text style={styles.braindumpCancel}>Fermer</Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      <Modal visible={!!overflowTask} transparent animationType="fade" onRequestClose={() => setOverflowTask(null)}>
        <View style={styles.braindumpBackdrop}>
          <View style={styles.overflowSheet}>
            <Text style={styles.overflowTitle} numberOfLines={1}>{overflowTask?.titre}</Text>
            <Pressable
              style={styles.overflowRow}
              onPress={() => {
                const task = overflowTask;
                setOverflowTask(null);
                if (task) gate('La synchronisation calendrier', () => addToCalendar(task));
              }}
            >
              <Ionicons name="calendar-outline" size={20} color={colors.text} />
              <Text style={styles.overflowRowText}>Synchroniser au calendrier</Text>
            </Pressable>
            {overflowTask?.statut !== 'fait' && (
              <Pressable
                style={styles.overflowRow}
                onPress={() => {
                  const task = overflowTask;
                  setOverflowTask(null);
                  if (task) reportToTomorrow(task.id);
                }}
              >
                <Ionicons name="arrow-redo-outline" size={20} color={colors.text} />
                <Text style={styles.overflowRowText}>Reporter à demain</Text>
              </Pressable>
            )}
            <Pressable style={{ marginTop: spacing.sm, alignSelf: 'center', minHeight: 44, justifyContent: 'center' }} onPress={() => setOverflowTask(null)}>
              <Text style={styles.braindumpCancel}>Annuler</Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      <Modal visible={modeCrashVisible} transparent animationType="fade" onRequestClose={() => setModeCrashVisible(false)}>
        <View style={styles.braindumpBackdrop}>
          <View style={styles.braindumpCard}>
            <Text style={styles.braindumpTitle}>🆘 Mode Crash</Text>
            <Text style={styles.braindumpSubtitle}>
              Quand tout devient trop, le mieux n'est pas de choisir quoi faire — c'est d'arrêter d'avoir à choisir. Avant toute chose : un verre d'eau, et quelques respirations si tu peux.
            </Text>
            <Pressable style={styles.crashSecondaryButton} onPress={() => { setModeCrashVisible(false); router.push('/respiration'); }}>
              <Text style={styles.crashSecondaryButtonText}>🫁 Respirer d’abord</Text>
            </Pressable>
            <Pressable style={styles.crashPrimaryButton} onPress={activerModeCrash}>
              <Text style={styles.crashPrimaryButtonText}>Tout mettre en pause pour aujourd’hui</Text>
            </Pressable>
            <Pressable onPress={() => setModeCrashVisible(false)} style={{ marginTop: spacing.md, alignSelf: 'center' }}>
              <Text style={styles.braindumpCancel}>Annuler</Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      <Modal visible={retourApresPauseVisible} transparent animationType="fade" onRequestClose={() => setRetourApresPauseVisible(false)}>
        <View style={styles.braindumpBackdrop}>
          <View style={styles.braindumpCard}>
            <Text style={styles.braindumpTitle}>👋 Content de te revoir</Text>
            <Text style={styles.braindumpSubtitle}>
              Ça fait {joursAbsence} jours — pas de souci, pas de compteur cassé. On peut repartir sur une seule micro-action aujourd'hui, le reste attend tranquillement.
            </Text>
            <Pressable style={styles.braindumpSubmit} onPress={() => { setRetourApresPauseVisible(false); confirmerAmnistie(); }}>
              <Text style={styles.braindumpSubmitText}>Repartir doucement</Text>
            </Pressable>
            <Pressable onPress={() => setRetourApresPauseVisible(false)} style={{ marginTop: spacing.md, alignSelf: 'center' }}>
              <Text style={styles.braindumpCancel}>Plus tard</Text>
            </Pressable>
          </View>
        </View>
      </Modal>

      <Modal
        visible={ghostReplyVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setGhostReplyVisible(false)}
      >
        <View style={styles.braindumpBackdrop}>
          <View style={styles.braindumpCard}>
            <Text style={styles.braindumpTitle}>Réponse à un message</Text>
            <Text style={styles.braindumpSubtitle}>
              Décris le message auquel tu n'as pas répondu et le contexte — l'IA propose un brouillon court, à toi de l'envoyer, le modifier ou l'ignorer.
            </Text>
            <TextInput
              style={styles.braindumpInput}
              multiline
              placeholder="Ex : ma collègue m'a demandé si je pouvais l'aider sur un dossier il y a 2 semaines, je n'ai jamais répondu..."
              placeholderTextColor={colors.textMuted}
              value={ghostReplyContext}
              onChangeText={setGhostReplyContext}
              autoFocus
            />
            {ghostReplyResult !== '' && (
              <View style={styles.ghostReplyResultBox}>
                <Text style={styles.ghostReplyResultText}>{ghostReplyResult}</Text>
                <Pressable onPress={copierReponseFantome} style={{ marginTop: spacing.sm, alignSelf: 'flex-start' }}>
                  <Text style={styles.refreshLink}>Copier</Text>
                </Pressable>
              </View>
            )}
            <View style={styles.braindumpActions}>
              <Pressable onPress={() => { setGhostReplyVisible(false); setGhostReplyContext(''); setGhostReplyResult(''); }}>
                <Text style={styles.braindumpCancel}>Fermer</Text>
              </Pressable>
              <Pressable style={styles.braindumpSubmit} onPress={submitGhostReply} disabled={ghostReplyLoading}>
                {ghostReplyLoading ? (
                  <ActivityIndicator color="#fff" size="small" />
                ) : (
                  <Text style={styles.braindumpSubmitText}>Générer</Text>
                )}
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>

      <Modal
        visible={assistantVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setAssistantVisible(false)}
      >
        <View style={styles.braindumpBackdrop}>
          <View style={styles.braindumpCard}>
            <Text style={styles.braindumpTitle}>Assistant</Text>
            <Text style={styles.braindumpSubtitle}>
              Dis-lui "je suis en retard, décale tout de 15 min", "reporte le ménage à demain", "mets les courses en priorité haute", ou juste "tout me semble urgent"...
            </Text>
            {assistantMessages.length > 0 && (
              <ScrollView style={styles.assistantScroll}>
                {assistantMessages.map((m, i) => (
                  <View key={i} style={[styles.assistantBubble, m.role === 'user' ? styles.assistantBubbleUser : styles.assistantBubbleAi]}>
                    <Text style={m.role === 'user' ? styles.assistantBubbleUserText : styles.assistantBubbleAiText}>{m.text}</Text>
                  </View>
                ))}
              </ScrollView>
            )}
            <View style={styles.inputPairRow}>
              <TextInput
                style={[styles.braindumpInput, { flex: 1, minHeight: 44 }]}
                placeholder="Écris ta demande..."
                placeholderTextColor={colors.textMuted}
                value={assistantInput}
                onChangeText={setAssistantInput}
                onSubmitEditing={submitAssistantMessage}
              />
              <Pressable style={styles.braindumpSubmit} onPress={submitAssistantMessage} disabled={assistantLoading}>
                {assistantLoading ? <ActivityIndicator color="#fff" size="small" /> : <Ionicons name="send" size={18} color="#fff" />}
              </Pressable>
            </View>
            <Pressable onPress={() => setAssistantVisible(false)} style={{ marginTop: spacing.md }}>
              <Text style={styles.braindumpCancel}>Fermer</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

function makeStyles(colors: ThemeColors) {
  const typography = makeTypography(colors);
  return StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingHorizontal: spacing.lg, paddingTop: spacing.lg },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background },
  title: { ...typography.title, marginBottom: spacing.xs },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  streakBadge: { backgroundColor: colors.accentMuted, borderRadius: radius.pill, paddingVertical: 3, paddingHorizontal: spacing.sm, marginBottom: spacing.xs },
  streakBadgeText: { color: colors.accent, fontFamily: fonts.bold, fontSize: 13 },
  energyGauge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    paddingVertical: 3,
    paddingHorizontal: spacing.sm,
    marginBottom: spacing.xs,
  },
  energyGaugeText: { color: colors.text, fontFamily: fonts.bold, fontSize: 13, fontVariant: ['tabular-nums'] },
  energyGaugeTrack: { width: 34, height: 6, borderRadius: 3, backgroundColor: colors.border, overflow: 'hidden' },
  energyGaugeFill: { height: '100%', borderRadius: 3 },
  weekRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.md },
  dayChip: { width: 38, alignItems: 'center', paddingVertical: 6, borderRadius: radius.md },
  dayChipActive: { backgroundColor: colors.primary, ...shadow.soft },
  dayChipLetter: { ...typography.caption, fontSize: 11, color: colors.textMuted },
  dayChipNumber: { ...typography.body, fontSize: 15, fontFamily: fonts.semibold, marginTop: 2 },
  dayChipTextActive: { color: '#fff' },
  dayChipDot: { width: 4, height: 4, borderRadius: 2, backgroundColor: colors.primary, marginTop: 3 },
  headerButtons: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.sm },
  grenouilleBanner: {
    backgroundColor: colors.accentMuted,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  grenouilleText: { ...typography.body, fontSize: 14, fontFamily: fonts.semibold, color: colors.text },
  grenouilleAction: { ...typography.caption, color: colors.accent, marginTop: 2, fontFamily: fonts.semibold },
  nudgeBanner: {
    backgroundColor: colors.primaryMuted,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  nudgeText: { ...typography.body, fontSize: 14, fontFamily: fonts.semibold, color: colors.text, marginBottom: spacing.xs },
  nudgeActions: { flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: spacing.md },
  nudgeDismiss: { color: colors.textMuted, fontSize: 13, fontFamily: fonts.medium },
  nudgeCta: { backgroundColor: colors.primary, borderRadius: radius.pill, paddingVertical: 6, paddingHorizontal: spacing.md },
  nudgeCtaText: { color: '#fff', fontSize: 13, fontFamily: fonts.semibold },
  dreadRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: spacing.xs },
  coachWarning: { backgroundColor: colors.accentMuted, borderRadius: radius.sm, padding: spacing.sm, marginTop: spacing.sm },
  coachWarningText: { ...typography.caption, fontSize: 12, color: colors.text },
  coachWarningButton: { marginTop: spacing.xs, alignSelf: 'flex-start' },
  coachWarningButtonText: { color: colors.warning, fontFamily: fonts.semibold, fontSize: 12 },
  dreadLabel: { ...typography.caption, fontSize: 11, marginRight: 2 },
  braindumpButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.primaryMuted,
    borderRadius: radius.pill,
    paddingVertical: 7,
    paddingHorizontal: spacing.sm + 2,
  },
  braindumpButtonText: { color: colors.primary, fontSize: 12, fontFamily: fonts.semibold },
  aiQuotaBadge: {
    fontSize: 10,
    color: colors.textMuted,
    backgroundColor: colors.surfaceAlt,
    borderRadius: 8,
    paddingHorizontal: 5,
    paddingVertical: 1,
    fontFamily: fonts.semibold,
  },
  toolQuotaBadge: { marginLeft: 'auto', fontSize: 11, color: colors.textMuted, fontFamily: fonts.semibold },
  premiumChip: {
    marginLeft: 'auto',
    backgroundColor: colors.accentMuted,
    borderRadius: radius.pill,
    paddingVertical: 2,
    paddingHorizontal: spacing.sm,
  },
  premiumChipText: { fontSize: 11, color: colors.accent, fontFamily: fonts.semibold },
  sectionHeaderRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: spacing.md, marginBottom: spacing.xs },
  sectionHeader: { ...typography.caption, textTransform: 'uppercase', letterSpacing: 0.5, fontFamily: fonts.bold },
  sectionCount: { fontFamily: fonts.regular, textTransform: 'none', letterSpacing: 0 },
  insight: { ...typography.caption, backgroundColor: colors.primaryMuted, padding: spacing.sm, borderRadius: 10, marginBottom: spacing.md, color: colors.primary },
  insightRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.md },
  retardButton: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingVertical: spacing.sm, paddingHorizontal: spacing.sm },
  retardButtonText: { color: colors.text, fontSize: 12, fontFamily: fonts.semibold },
  retardPicker: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.md },
  retardChip: { backgroundColor: colors.primaryMuted, borderRadius: 16, paddingVertical: 6, paddingHorizontal: spacing.md },
  retardChipText: { color: colors.primary, fontSize: 13, fontFamily: fonts.semibold },
  empty: { ...typography.body, color: colors.textMuted, marginTop: spacing.lg },
  caption: { ...typography.caption, marginTop: spacing.xs },
  taskCard: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...shadow.soft,
  },
  taskCardDone: { opacity: 0.6 },
  reorderColumn: { justifyContent: 'center', alignItems: 'center', gap: 2, marginRight: spacing.sm },
  taskBody: { flex: 1 },
  taskHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  taskHeaderMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  overflowButton: { alignItems: 'center', justifyContent: 'center' },
  taskIconBubble: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center' },
  taskIconEmoji: { fontSize: 16 },
  taskIconCheckBadge: { position: 'absolute', bottom: -3, right: -3, backgroundColor: colors.surface, borderRadius: 8 },
  taskTitle: { ...typography.body, fontFamily: fonts.semibold, flex: 1 },
  taskTitleDone: { textDecorationLine: 'line-through', color: colors.textMuted },
  estimationRow: { marginTop: spacing.sm },
  inputPairRow: { flexDirection: 'row', gap: spacing.sm },
  estimationInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    padding: spacing.sm,
    fontSize: 14,
    fontFamily: fonts.regular,
    color: colors.text,
  },
  taxeSuggestion: { ...typography.caption, color: colors.accent, marginTop: spacing.xs, fontFamily: fonts.semibold },
  siAlorsAddLink: { ...typography.caption, color: colors.primary, marginTop: spacing.sm, fontFamily: fonts.semibold },
  siAlorsChip: { backgroundColor: colors.primaryMuted, borderRadius: radius.sm, padding: spacing.sm, marginTop: spacing.sm, alignSelf: 'flex-start' },
  siAlorsChipText: { ...typography.caption, color: colors.primary, fontFamily: fonts.semibold },
  siAlorsSaveButton: { backgroundColor: colors.primary, borderRadius: radius.sm, width: 40, alignItems: 'center', justifyContent: 'center' },
  subtaskRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.sm, marginLeft: spacing.lg },
  subtaskText: { ...typography.body, fontSize: 14, flex: 1 },
  granulariteRow: { flexDirection: 'row', gap: spacing.xs, marginTop: spacing.sm },
  granulariteChip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 20,
    paddingVertical: 4,
    paddingHorizontal: spacing.sm,
  },
  granulariteChipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
  granulariteText: { fontSize: 12, color: colors.textMuted },
  granulariteTextActive: { color: colors.primary, fontFamily: fonts.semibold },
  decomposeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.sm,
    alignSelf: 'flex-start',
  },
  decomposeText: { color: colors.primary, fontSize: 14, fontFamily: fonts.medium },
  braindumpBackdrop: { flex: 1, backgroundColor: 'rgba(28,27,41,0.45)', justifyContent: 'flex-end' },
  braindumpCard: { backgroundColor: colors.surface, borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: spacing.lg, paddingBottom: spacing.xl, ...shadow.card },
  overflowSheet: { backgroundColor: colors.surface, borderTopLeftRadius: radius.xl, borderTopRightRadius: radius.xl, padding: spacing.lg, paddingBottom: spacing.xl, ...shadow.card },
  overflowTitle: { ...typography.caption, color: colors.textMuted, marginBottom: spacing.sm },
  overflowRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.md, minHeight: 44 },
  overflowRowText: { ...typography.body, fontFamily: fonts.medium },
  braindumpTitle: { ...typography.heading, marginBottom: spacing.xs },
  braindumpSubtitle: { ...typography.caption, marginBottom: spacing.md },
  braindumpScopeRow: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.md },
  braindumpScopeChip: { borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingVertical: 6, paddingHorizontal: spacing.md },
  braindumpScopeChipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
  braindumpScopeText: { fontSize: 13, color: colors.textMuted },
  braindumpScopeTextActive: { color: colors.primary, fontFamily: fonts.semibold },
  braindumpInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    minHeight: 110,
    textAlignVertical: 'top',
    fontSize: 15,
    fontFamily: fonts.regular,
    color: colors.text,
    backgroundColor: colors.background,
  },
  toolRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  toolRowText: { ...typography.body, fontSize: 15 },
  assistantScroll: { maxHeight: 220, marginBottom: spacing.sm },
  assistantBubble: { borderRadius: radius.md, padding: spacing.sm, marginBottom: spacing.xs, maxWidth: '85%' },
  assistantBubbleUser: { backgroundColor: colors.primary, alignSelf: 'flex-end' },
  assistantBubbleAi: { backgroundColor: colors.primaryMuted, alignSelf: 'flex-start' },
  assistantBubbleUserText: { color: '#fff', fontSize: 14, fontFamily: fonts.regular },
  assistantBubbleAiText: { color: colors.text, fontSize: 14, fontFamily: fonts.regular },
  colorRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.md },
  colorSwatch: { width: 32, height: 32, borderRadius: 16, borderWidth: 2, borderColor: 'transparent' },
  colorSwatchActive: { borderColor: colors.primary },
  iconGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  iconChoice: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  braindumpActions: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: spacing.md },
  braindumpCancel: { color: colors.textMuted, fontSize: 14 },
  braindumpSubmit: { backgroundColor: colors.primary, borderRadius: 20, paddingVertical: spacing.sm, paddingHorizontal: spacing.lg },
  braindumpSubmitText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 14 },
  crashSecondaryButton: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginBottom: spacing.sm,
  },
  crashSecondaryButtonText: { color: colors.text, fontFamily: fonts.semibold, fontSize: 15 },
  crashPrimaryButton: { backgroundColor: colors.danger, borderRadius: radius.md, paddingVertical: spacing.md, alignItems: 'center' },
  crashPrimaryButtonText: { color: '#fff', fontFamily: fonts.semibold, fontSize: 15 },
  ghostReplyResultBox: { backgroundColor: colors.primaryMuted, borderRadius: radius.md, padding: spacing.md, marginTop: spacing.md },
  ghostReplyResultText: { ...typography.body, fontSize: 14 },
  refreshLink: { color: colors.primary, fontSize: 13, fontFamily: fonts.semibold },
  });
}
