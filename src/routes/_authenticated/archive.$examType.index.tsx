import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { BookText } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { BreadcrumbNav } from "@/components/library/breadcrumb-nav";
import { filieresQueryOptions, subjectsQueryOptions, type ExamType } from "@/lib/queries/archive";

const VALID_TYPES = new Set(["bem", "bac"]);

export const Route = createFileRoute("/_authenticated/archive/$examType/")({
  beforeLoad: ({ params }) => {
    if (!VALID_TYPES.has(params.examType)) throw notFound();
  },
  component: SubjectPicker,
});

function SubjectPicker() {
  const { examType } = Route.useParams();
  const type = examType as ExamType;
  const { data: filieres, isLoading: filieresLoading } = useQuery(filieresQueryOptions(type));
  const [selectedFiliere, setSelectedFiliere] = useState<string | null>(null);
  const { data: subjects, isLoading: subjectsLoading } = useQuery(subjectsQueryOptions(type, selectedFiliere));

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <BreadcrumbNav items={[{ label: "Archive", to: "/archive" }, { label: type.toUpperCase() }]} />
      <h1 className="mt-2 font-display text-2xl font-bold tracking-tight sm:text-3xl">{type.toUpperCase()}</h1>

      {!filieresLoading && filieres && filieres.length > 0 && (
        <div className="mt-6 flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedFiliere(null)}
            className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors ${
              selectedFiliere === null ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:bg-secondary"
            }`}
          >
            Toutes filières
          </button>
          {filieres.map((f) => (
            <button
              key={f}
              onClick={() => setSelectedFiliere(f)}
              className={`rounded-full border px-3.5 py-1.5 text-xs font-medium capitalize transition-colors ${
                selectedFiliere === f ? "border-primary bg-primary/10 text-primary" : "border-border text-muted-foreground hover:bg-secondary"
              }`}
            >
              {f.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      )}

      {subjectsLoading ? (
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-16" />
          ))}
        </div>
      ) : subjects && subjects.length > 0 ? (
        <StaggerGroup className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {subjects.map((subject) => (
            <StaggerItem key={subject}>
              <Link
                to="/archive/$examType/$subject"
                params={{ examType, subject }}
                search={{ filiere: selectedFiliere ?? undefined }}
              >
                <Card className="hover-lift flex items-center gap-3 p-4">
                  <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary/12 text-primary">
                    <BookText className="size-4" />
                  </div>
                  <h2 className="text-sm font-semibold capitalize">{subject.replace(/_/g, " ")}</h2>
                </Card>
              </Link>
            </StaggerItem>
          ))}
        </StaggerGroup>
      ) : (
        <p className="mt-10 text-sm text-muted-foreground">
          Aucun sujet publié {selectedFiliere ? "pour cette filière" : "pour le moment"}.
        </p>
      )}
    </div>
  );
}
