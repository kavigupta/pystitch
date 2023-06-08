
Section programs.

Variable var : Set.

Variable expr : Set.

Variable effect : Set.

Variable value : Set.

Variable truthy : value -> bool.

Definition environment := list (var * value).

(* Fix this so it catches red undant variables *)
Definition equal_env := fun (x : environment) y => x = y.

Variable exec_e : environment -> expr -> value -> list effect -> Prop.

Inductive prog :=
  | prog_e : expr -> prog
  | prog_a : var -> expr -> prog
  (* add multi-assignment *)
  | prog_s : prog -> prog -> prog
  | prog_i : expr -> prog -> prog -> prog
  | prog_w : expr -> prog -> prog -> prog
  (* add while/for/try/def *)
.

Inductive exec_p : environment -> prog -> environment -> list effect -> Prop :=
  | exec_p_e
    : forall env_1 env_2 effs e,
      (exists x, exec_e env_1 e x effs) -> equal_env env_1 env_2 -> exec_p env_1 (prog_e e) env_2 effs
  | exec_p_a
    : forall env_1 env_2 effs v e,
      (exists x, exec_e env_1 e x effs /\ env_2 = cons (v, x) env_1) -> exec_p env_1 (prog_a v e) env_2 effs
  | exec_p_s
    : forall env_1 env_2 effs p_1 p_2,
      (exists env_inter eff_1 eff_2,
        exec_p env_1 p_1 env_inter eff_1 /\ exec_p env_inter p_2 env_2 eff_2 /\ app eff_1 eff_2 = effs
      ) -> exec_p env_1 (prog_s p_1 p_2) env_2 effs
  | exec_p_i
    : forall env_1 env_2 effs cond p_1 p_2,
      (exists x eff_1 eff_2,
        exec_e env_1 cond x eff_1 /\ exec_p env_1 (if truthy x then p_1 else p_2) env_2 eff_2 /\ app eff_1 eff_2 = effs
      ) -> exec_p env_1 (prog_i cond p_1 p_2) env_2 effs
.

Hypothesis exec_e_deterministic : forall {env e x_a effs_a x_b effs_b},
  exec_e env e x_a effs_a -> exec_e env e x_b effs_b -> x_a = x_b /\ effs_a = effs_b.

Theorem exec_p_deterministic : forall p env_1 env_2a effs_a env_2b effs_b,
  exec_p env_1 p env_2a effs_a -> exec_p env_1 p env_2b effs_b -> equal_env env_2a env_2b /\ effs_a = effs_b.

  induction p; intros; inversion H; inversion H0; subst.
  all: repeat match goal with
    | [H: exists _, _ |- _] => destruct H
    | [H: _ /\ _ |- _] => destruct H
    end.
  all: try match goal with
    | [H1: exec_e _ _ _ _, H2: exec_e _ _ _ _ |- _] => destruct (exec_e_deterministic H2 H1)
    end.
  all: unfold equal_env in *.
  all: subst.
  all: try solve [split; auto].
  - destruct (IHp1 _ _ _ _ _ H2 H1); subst.
    destruct (IHp2 _ _ _ _ _ H5 H3); subst.
    split; auto.
  - destruct (truthy x2); simpl in *.
    destruct (IHp1 _ _ _ _ _ H3 H5).
    subst; split; auto.
    destruct (IHp2 _ _ _ _ _ H3 H5).
    subst; split; auto.
Qed.

End programs.

Type prog.