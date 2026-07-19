import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Plus, Users, KeyRound } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { myGroupsQueryOptions } from "@/lib/queries/groups";
import { useCreateGroup, useJoinGroupByCode } from "@/hooks/use-group-actions";

export const Route = createFileRoute("/_authenticated/groups/")({
  component: GroupsIndex,
});

function GroupsIndex() {
  const { user } = Route.useRouteContext();
  const { data: groups, isLoading } = useQuery(myGroupsQueryOptions(user.id));

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">Groupes d'étude</h1>
          <p className="mt-1 text-muted-foreground">Révise avec ta classe ou tes amis.</p>
        </div>
        <div className="flex gap-2">
          <JoinGroupDialog userId={user.id} />
          <CreateGroupDialog ownerId={user.id} />
        </div>
      </div>

      <div className="mt-8">
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28" />
            ))}
          </div>
        ) : groups && groups.length > 0 ? (
          <StaggerGroup className="grid gap-4 sm:grid-cols-2">
            {groups.map((g) => (
              <StaggerItem key={g.id}>
                <Link to="/groups/$groupId" params={{ groupId: g.id }}>
                  <Card className="hover-lift h-full p-5">
                    <h2 className="font-display text-sm font-semibold">{g.name}</h2>
                    <p className="mt-1 text-xs text-muted-foreground">{g.subject} · {g.level}</p>
                    <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <Users className="size-3.5" /> {g.memberCount}/{g.max_members}
                      </span>
                      <span className="font-mono">{g.invite_code}</span>
                    </div>
                  </Card>
                </Link>
              </StaggerItem>
            ))}
          </StaggerGroup>
        ) : (
          <Card className="p-8 text-center">
            <p className="text-sm text-muted-foreground">
              Tu n'as pas encore de groupe. Crée-en un ou rejoins-en un avec un code.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}

function CreateGroupDialog({ ownerId }: { ownerId: string }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [level, setLevel] = useState("");
  const [description, setDescription] = useState("");
  const create = useCreateGroup(ownerId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await create.mutateAsync({ name, subject, level, description: description || null, maxMembers: 20 });
      toast.success("Groupe créé !");
      setOpen(false);
      setName("");
      setSubject("");
      setLevel("");
      setDescription("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Impossible de créer ce groupe.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="size-4" /> Créer
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouveau groupe</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="name">Nom</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="subject">Matière</Label>
              <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="level">Niveau</Label>
              <Input id="level" value={level} onChange={(e) => setLevel(e.target.value)} placeholder="3AS Sciences" required />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="description">
              Description <span className="font-normal text-muted-foreground">(optionnel)</span>
            </Label>
            <Textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </div>
          <Button type="submit" disabled={create.isPending} className="w-full">
            {create.isPending ? "Création…" : "Créer le groupe"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function JoinGroupDialog({ userId }: { userId: string }) {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const join = useJoinGroupByCode(userId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const { groupName } = await join.mutateAsync(code);
      toast.success(`Tu as rejoint « ${groupName} » !`);
      setOpen(false);
      setCode("");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Code invalide.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <KeyRound className="size-4" /> Rejoindre
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Rejoindre un groupe</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="code">Code d'invitation</Label>
            <Input id="code" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} className="font-mono" required />
          </div>
          <Button type="submit" disabled={join.isPending} className="w-full">
            {join.isPending ? "…" : "Rejoindre"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
