import { useCallback, useEffect, useMemo, useState } from 'react';
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
import { useRouter } from 'expo-router';
import { supabase } from '../../lib/supabase/client';
import { breakdownTask } from '../../lib/ai/breakdownTask';
import { planFromBraindump, planWeekFromBraindump } from '../../lib/ai/braindump';
import { interpretScheduleCommand } from '../../lib/ai/scheduleAssistant';
import { getHighDreadMomentStats, type MomentStats } from '../../lib/supabase/momentStats';
import { colors, spacing, typography } from '../../constants/theme';
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
  subtasks: Subtask[];
};

const today = () => new Date().toISOString().slice(0, 10);
const GRANULARITE_LABELS: Record<1 | 2 | 3, string> = { 1: 'Grandes lignes', 2: 'Standard', 3: 'Petits pas' };
const PRIORITE_CYCLE: (Task['niveau_priorite'])[] = [null, 'haute', 'moyenne', 'basse'];
const PRIORITE_COLOR: Record<'haute' | 'moyenne' | 'basse', string> = {
  haute: '#D9534F',
  moyenne: colors.warning,
  basse: colors.textMuted,
};
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
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newTitle, setNewTitle] = useState('');
  const [estimationInput, setEstimationInput] = useState<Record<string, string>>({});
  const [timeInput, setTimeInput] = useState<Record<string, string>>({});
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
  const [assistantVisible, setAssistantVisible] = useState(false);
  const [assistantInput, setAssistantInput] = useState('');
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantMessages, setAssistantMessages] = useState<{ role: 'user' | 'assistant'; text: string }[]>([]);
  const [toolsMenuVisible, setToolsMenuVisible] = useState(false);

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
        .select('id, titre, statut, estimation_minutes, temps_reel_minutes, moment_journee, niveau_dread, niveau_priorite, heure_debut, ordre, icone_manuelle, couleur_manuelle, subtasks(id, titre, fait, ordre)')
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
      .select('jours_consecutifs')
      .eq('user_id', session.user.id)
      .single()
      .then(({ data }) => setStreakDays(data?.jours_consecutifs ?? null));
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
      const lieu = braindumpScope === 'semaine' ? 'ta semaine' : 'ta journée';
      Alert.alert('Planning généré', `${count} tâche${count > 1 ? 's' : ''} ajoutée${count > 1 ? 's' : ''} à ${lieu}.`);
    } catch {
      Alert.alert('L’IA n’a pas pu générer ton planning', 'Réessaie dans un instant, ou ajoute tes tâches une par une.');
    } finally {
      setBraindumpLoading(false);
    }
  }

  async function addTask() {
    if (!newTitle.trim() || !session) return;
    const { error } = await supabase.from('tasks').insert({
      user_id: session.user.id,
      titre: newTitle.trim(),
      date_prevue: selectedDate,
    });
    if (error) {
      Alert.alert('Erreur', error.message);
      return;
    }
    setNewTitle('');
    loadTasks();
  }

  async function saveEstimation(taskId: string) {
    const value = parseInt(estimationInput[taskId] ?? '', 10);
    if (!value || Number.isNaN(value)) return;
    await supabase.from('tasks').update({ estimation_minutes: value, statut: 'en_cours' }).eq('id', taskId);
    loadTasks();
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

  // Menu "Outils" : regroupe les actions secondaires derrière un seul bouton
  // plutôt que d'aligner 6 chips en permanence dans l'en-tête — la ligne de
  // boutons avait fini par déborder sur deux lignes au fil des ajouts.
  const TOOLS: { icon: keyof typeof Ionicons.glyphMap; label: string; onPress: () => void }[] = [
    { icon: 'sparkles-outline', label: 'Assistant', onPress: () => setAssistantVisible(true) },
    { icon: 'albums-outline', label: 'Backlog', onPress: () => router.push('/backlog') },
    { icon: 'repeat-outline', label: 'Routines', onPress: () => router.push('/routines') },
    { icon: 'moon-outline', label: 'Fin de journée', onPress: () => router.push('/rituel-fin-journee') },
    { icon: 'leaf-outline', label: 'Respirer', onPress: () => router.push('/respiration') },
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
      </View>

      <View style={styles.weekRow}>
        <Pressable hitSlop={8} onPress={() => shiftWeek(-7)}>
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
        <Pressable hitSlop={8} onPress={() => shiftWeek(7)}>
          <Ionicons name="chevron-forward" size={18} color={colors.textMuted} />
        </Pressable>
      </View>

      <View style={styles.headerButtons}>
        <Pressable style={styles.braindumpButton} onPress={() => setBraindumpVisible(true)}>
          <Ionicons name="chatbubble-ellipses-outline" size={16} color={colors.primary} />
          <Text style={styles.braindumpButtonText}>Vide-tête</Text>
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
              <Pressable hitSlop={4} disabled={index === 0} onPress={() => moveTask(section.data, item.id, -1)}>
                <Ionicons name="chevron-up" size={16} color={index === 0 ? colors.border : colors.textMuted} />
              </Pressable>
              <Pressable hitSlop={4} disabled={index === section.data.length - 1} onPress={() => moveTask(section.data, item.id, 1)}>
                <Ionicons name="chevron-down" size={16} color={index === section.data.length - 1 ? colors.border : colors.textMuted} />
              </Pressable>
            </View>
            <View style={styles.taskBody}>
            <View style={styles.taskHeader}>
              {item.statut !== 'fait' && (
                <Pressable hitSlop={6} onPress={() => cyclePriorite(item)}>
                  <Ionicons
                    name={item.niveau_priorite ? 'flag' : 'flag-outline'}
                    size={16}
                    color={item.niveau_priorite ? PRIORITE_COLOR[item.niveau_priorite] : colors.border}
                  />
                </Pressable>
              )}
              <Pressable
                hitSlop={4}
                onPress={() => {
                  setPickerColor(resolveTaskIcon(item).color);
                  setIconPickerTaskId(item.id);
                }}
              >
                <View style={[styles.taskIconBubble, { backgroundColor: resolveTaskIcon(item).color }]}>
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
                <Pressable hitSlop={8} onPress={() => startFocusOn(item)}>
                  <Ionicons name="play-circle-outline" size={20} color={colors.textMuted} />
                </Pressable>
              )}
              <Pressable hitSlop={8} onPress={() => addToCalendar(item)}>
                <Ionicons name="calendar-outline" size={18} color={colors.textMuted} />
              </Pressable>
              {item.statut !== 'fait' && (
                <Pressable hitSlop={8} onPress={() => reportToTomorrow(item.id)}>
                  <Ionicons name="arrow-redo-outline" size={18} color={colors.textMuted} />
                </Pressable>
              )}
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

      <View style={styles.addRow}>
        <TextInput
          style={styles.addInput}
          placeholder="Ajouter une tâche..."
          placeholderTextColor={colors.textMuted}
          value={newTitle}
          onChangeText={setNewTitle}
          onSubmitEditing={addTask}
        />
        <Pressable style={styles.addButton} onPress={addTask}>
          <Ionicons name="add" size={24} color="#fff" />
        </Pressable>
      </View>

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
              </Pressable>
            ))}
            <Pressable onPress={() => setToolsMenuVisible(false)} style={{ marginTop: spacing.sm }}>
              <Text style={styles.braindumpCancel}>Fermer</Text>
            </Pressable>
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

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, paddingHorizontal: spacing.lg, paddingTop: spacing.lg },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background },
  title: { ...typography.title, marginBottom: spacing.xs },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  streakBadge: { backgroundColor: colors.primaryMuted, borderRadius: 14, paddingVertical: 3, paddingHorizontal: spacing.sm, marginBottom: spacing.xs },
  streakBadgeText: { color: colors.primary, fontWeight: '700', fontSize: 13 },
  weekRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.md },
  dayChip: { width: 38, alignItems: 'center', paddingVertical: 6, borderRadius: 12 },
  dayChipActive: { backgroundColor: colors.primary },
  dayChipLetter: { ...typography.caption, fontSize: 11, color: colors.textMuted },
  dayChipNumber: { ...typography.body, fontSize: 15, fontWeight: '600', marginTop: 2 },
  dayChipTextActive: { color: '#fff' },
  dayChipDot: { width: 4, height: 4, borderRadius: 2, backgroundColor: colors.primary, marginTop: 3 },
  headerButtons: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.sm },
  grenouilleBanner: {
    backgroundColor: '#FBEFE3',
    borderRadius: 12,
    padding: spacing.sm,
    marginBottom: spacing.md,
  },
  grenouilleText: { ...typography.body, fontSize: 14, fontWeight: '600', color: colors.text },
  grenouilleAction: { ...typography.caption, color: colors.warning, marginTop: 2, fontWeight: '600' },
  dreadRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: spacing.xs },
  coachWarning: { backgroundColor: '#FBEFE3', borderRadius: 10, padding: spacing.sm, marginTop: spacing.sm },
  coachWarningText: { ...typography.caption, fontSize: 12, color: colors.text },
  coachWarningButton: { marginTop: spacing.xs, alignSelf: 'flex-start' },
  coachWarningButtonText: { color: colors.warning, fontWeight: '600', fontSize: 12 },
  dreadLabel: { ...typography.caption, fontSize: 11, marginRight: 2 },
  braindumpButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.primaryMuted,
    borderRadius: 20,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
  },
  braindumpButtonText: { color: colors.primary, fontSize: 12, fontWeight: '600' },
  sectionHeaderRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: spacing.md, marginBottom: spacing.xs },
  sectionHeader: { ...typography.caption, textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: '700' },
  sectionCount: { fontWeight: '400', textTransform: 'none', letterSpacing: 0 },
  insight: { ...typography.caption, backgroundColor: colors.primaryMuted, padding: spacing.sm, borderRadius: 10, marginBottom: spacing.md, color: colors.primary },
  insightRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.md },
  retardButton: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingVertical: spacing.sm, paddingHorizontal: spacing.sm },
  retardButtonText: { color: colors.text, fontSize: 12, fontWeight: '600' },
  retardPicker: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.md },
  retardChip: { backgroundColor: colors.primaryMuted, borderRadius: 16, paddingVertical: 6, paddingHorizontal: spacing.md },
  retardChipText: { color: colors.primary, fontSize: 13, fontWeight: '600' },
  empty: { ...typography.body, color: colors.textMuted, marginTop: spacing.lg },
  caption: { ...typography.caption, marginTop: spacing.xs },
  taskCard: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: 14,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  taskCardDone: { opacity: 0.6 },
  reorderColumn: { justifyContent: 'center', alignItems: 'center', gap: 2, marginRight: spacing.sm },
  taskBody: { flex: 1 },
  taskHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  taskHeaderMain: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  taskIconBubble: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center' },
  taskIconEmoji: { fontSize: 16 },
  taskIconCheckBadge: { position: 'absolute', bottom: -3, right: -3, backgroundColor: colors.surface, borderRadius: 8 },
  taskTitle: { ...typography.body, fontWeight: '600', flex: 1 },
  taskTitleDone: { textDecorationLine: 'line-through', color: colors.textMuted },
  estimationRow: { marginTop: spacing.sm },
  inputPairRow: { flexDirection: 'row', gap: spacing.sm },
  estimationInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: spacing.sm,
    fontSize: 14,
    color: colors.text,
  },
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
  granulariteTextActive: { color: colors.primary, fontWeight: '600' },
  decomposeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.sm,
    alignSelf: 'flex-start',
  },
  decomposeText: { color: colors.primary, fontSize: 14, fontWeight: '500' },
  addRow: { flexDirection: 'row', gap: spacing.sm, paddingVertical: spacing.md },
  addInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: spacing.md,
    fontSize: 16,
    color: colors.text,
  },
  addButton: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: colors.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  braindumpBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'flex-end' },
  braindumpCard: { backgroundColor: colors.surface, borderTopLeftRadius: 24, borderTopRightRadius: 24, padding: spacing.lg, paddingBottom: spacing.xl },
  braindumpTitle: { ...typography.heading, marginBottom: spacing.xs },
  braindumpSubtitle: { ...typography.caption, marginBottom: spacing.md },
  braindumpScopeRow: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.md },
  braindumpScopeChip: { borderWidth: 1, borderColor: colors.border, borderRadius: 20, paddingVertical: 6, paddingHorizontal: spacing.md },
  braindumpScopeChipActive: { backgroundColor: colors.primaryMuted, borderColor: colors.primary },
  braindumpScopeText: { fontSize: 13, color: colors.textMuted },
  braindumpScopeTextActive: { color: colors.primary, fontWeight: '600' },
  braindumpInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: spacing.md,
    minHeight: 110,
    textAlignVertical: 'top',
    fontSize: 15,
    color: colors.text,
    backgroundColor: colors.background,
  },
  toolRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border },
  toolRowText: { ...typography.body, fontSize: 15 },
  assistantScroll: { maxHeight: 220, marginBottom: spacing.sm },
  assistantBubble: { borderRadius: 12, padding: spacing.sm, marginBottom: spacing.xs, maxWidth: '85%' },
  assistantBubbleUser: { backgroundColor: colors.primary, alignSelf: 'flex-end' },
  assistantBubbleAi: { backgroundColor: colors.primaryMuted, alignSelf: 'flex-start' },
  assistantBubbleUserText: { color: '#fff', fontSize: 14 },
  assistantBubbleAiText: { color: colors.text, fontSize: 14 },
  colorRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.md },
  colorSwatch: { width: 32, height: 32, borderRadius: 16, borderWidth: 2, borderColor: 'transparent' },
  colorSwatchActive: { borderColor: colors.primary },
  iconGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  iconChoice: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  braindumpActions: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: spacing.md },
  braindumpCancel: { color: colors.textMuted, fontSize: 14 },
  braindumpSubmit: { backgroundColor: colors.primary, borderRadius: 20, paddingVertical: spacing.sm, paddingHorizontal: spacing.lg },
  braindumpSubmitText: { color: '#fff', fontWeight: '600', fontSize: 14 },
});
